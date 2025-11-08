"""
Packer-InfoFinder v2.0 - Incremental Caching System
High-performance caching for large JavaScript file analysis

Optimized for handling massive files like 22MB GitHub CLI index.js
with intelligent chunking and change detection.
"""

import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import pickle
import os


class CacheStrategy(Enum):
    """Cache eviction strategies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    ADAPTIVE = "adaptive"


class ChunkingStrategy(Enum):
    """Strategies for splitting large files into chunks"""
    FIXED_SIZE = "fixed_size"
    FUNCTION_BASED = "function_based"
    SEMANTIC_BASED = "semantic_based"
    ADAPTIVE = "adaptive"


@dataclass
class CacheEntry:
    """Represents a cached analysis result"""
    key: str
    data: Any
    size: int
    created: float
    last_accessed: float
    access_count: int
    checksum: str
    ttl: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if self.ttl is None:
            return False
        return time.time() > self.created + self.ttl


@dataclass
class ChunkInfo:
    """Information about a code chunk"""
    index: int
    content: str
    hash: str
    start_pos: int
    end_pos: int
    overlap_start: int = 0
    overlap_end: int = 0


class IncrementalCacheManager:
    """
    High-performance incremental cache manager for JavaScript analysis
    
    Features:
    - Multi-tier caching (memory + disk)
    - Intelligent chunking strategies
    - Change detection and incremental updates
    - LRU/LFU/FIFO eviction policies
    - Compression support
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize cache manager with configuration"""
        self.config = config or {}
        
        # Cache settings
        self.cache_dir = Path(self.config.get('cache_directory', './cache'))
        self.max_memory_size = self.config.get('max_memory_size', 256 * 1024 * 1024)  # 256MB
        self.max_disk_size = self.config.get('max_disk_size', 1024 * 1024 * 1024)  # 1GB
        self.default_ttl = self.config.get('default_ttl', 3600)  # 1 hour
        
        # Chunking settings
        self.chunk_size = self.config.get('chunk_size', 1024 * 1024)  # 1MB
        self.overlap_size = self.config.get('overlap_size', 1024)  # 1KB
        self.chunking_strategy = ChunkingStrategy(
            self.config.get('chunking_strategy', 'fixed_size')
        )
        
        # Cache strategy
        self.cache_strategy = CacheStrategy(
            self.config.get('cache_strategy', 'lru')
        )
        
        # Internal state
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []  # For LRU
        self.access_frequency: Dict[str, int] = {}  # For LFU
        self.current_memory_size = 0
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'chunks_processed': 0,
            'chunks_cached': 0
        }
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached data by key"""
        # Check memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not entry.is_expired():
                self._update_access_stats(key)
                self.stats['hits'] += 1
                return entry.data
            else:
                # Remove expired entry
                await self._remove_from_memory(key)
        
        # Check disk cache
        disk_data = await self._get_from_disk(key)
        if disk_data is not None:
            # Promote to memory cache
            await self.set(key, disk_data, promote_to_memory=True)
            self.stats['hits'] += 1
            return disk_data
        
        self.stats['misses'] += 1
        return None
    
    async def set(self, key: str, data: Any, ttl: Optional[float] = None, 
                  promote_to_memory: bool = True) -> None:
        """Set cached data"""
        serialized_data = pickle.dumps(data)
        size = len(serialized_data)
        checksum = hashlib.sha256(serialized_data).hexdigest()
        
        entry = CacheEntry(
            key=key,
            data=data,
            size=size,
            created=time.time(),
            last_accessed=time.time(),
            access_count=1,
            checksum=checksum,
            ttl=ttl or self.default_ttl
        )
        
        if promote_to_memory:
            await self._set_in_memory(key, entry)
        
        # Always save to disk for persistence
        await self._set_on_disk(key, data)
    
    async def analyze_incremental(self, key: str, content: str, 
                                  analyzer: Callable[[str, Dict[str, Any]], Any]) -> Any:
        """
        Perform incremental analysis on large content
        
        Args:
            key: Cache key for the content
            content: Large JavaScript content to analyze
            analyzer: Function to analyze each chunk
            
        Returns:
            Merged analysis result
        """
        # Create chunks
        chunks = self._create_chunks(content)
        
        # Analyze each chunk
        chunk_results = []
        for i, chunk in enumerate(chunks):
            chunk_key = f"{key}_chunk_{i}"
            chunk_hash = hashlib.sha256(chunk.content.encode()).hexdigest()
            
            # Check if chunk is cached and unchanged
            cached_result = await self.get(chunk_key)
            cached_hash = await self.get(f"{chunk_key}_hash")
            
            if cached_result is not None and cached_hash == chunk_hash:
                # Use cached result
                chunk_results.append(cached_result)
                self.stats['chunks_cached'] += 1
            else:
                # Analyze chunk
                context = {
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'chunk_hash': chunk_hash,
                    'previous_result': chunk_results[-1] if chunk_results else None
                }
                
                result = await analyzer(chunk.content, context)
                chunk_results.append(result)
                
                # Cache result and hash
                await self.set(chunk_key, result)
                await self.set(f"{chunk_key}_hash", chunk_hash)
                
                self.stats['chunks_processed'] += 1
        
        # Merge chunk results
        merged_result = self._merge_chunk_results(chunk_results)
        
        # Cache final result
        await self.set(key, merged_result)
        
        return merged_result
    
    def _create_chunks(self, content: str) -> List[ChunkInfo]:
        """Create chunks from content based on strategy"""
        if self.chunking_strategy == ChunkingStrategy.FIXED_SIZE:
            return self._create_fixed_size_chunks(content)
        elif self.chunking_strategy == ChunkingStrategy.FUNCTION_BASED:
            return self._create_function_based_chunks(content)
        elif self.chunking_strategy == ChunkingStrategy.SEMANTIC_BASED:
            return self._create_semantic_chunks(content)
        else:  # ADAPTIVE
            return self._create_adaptive_chunks(content)
    
    def _create_fixed_size_chunks(self, content: str) -> List[ChunkInfo]:
        """Create fixed-size chunks with overlap"""
        chunks = []
        content_length = len(content)
        
        start = 0
        chunk_index = 0
        
        while start < content_length:
            # Calculate chunk boundaries
            end = min(start + self.chunk_size, content_length)
            
            # Add overlap from previous chunk
            overlap_start = max(0, start - self.overlap_size) if start > 0 else 0
            
            # Add overlap for next chunk
            overlap_end = min(end + self.overlap_size, content_length) if end < content_length else end
            
            # Extract chunk content
            chunk_content = content[overlap_start:overlap_end]
            chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()
            
            chunks.append(ChunkInfo(
                index=chunk_index,
                content=chunk_content,
                hash=chunk_hash,
                start_pos=start,
                end_pos=end,
                overlap_start=overlap_start,
                overlap_end=overlap_end
            ))
            
            start = end
            chunk_index += 1
        
        return chunks
    
    def _create_function_based_chunks(self, content: str) -> List[ChunkInfo]:
        """Create chunks based on function boundaries"""
        # Find function boundaries using regex
        import re
        
        function_pattern = r'(?:^|\n)(?:function\s+\w+|const\s+\w+\s*=\s*(?:function|\(.*?\)\s*=>))'
        matches = list(re.finditer(function_pattern, content, re.MULTILINE))
        
        if not matches:
            # Fallback to fixed-size chunks
            return self._create_fixed_size_chunks(content)
        
        chunks = []
        chunk_index = 0
        
        for i, match in enumerate(matches):
            start_pos = match.start()
            
            # Find end position (start of next function or end of content)
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(content)
            
            # Extract function content
            chunk_content = content[start_pos:end_pos]
            chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()
            
            chunks.append(ChunkInfo(
                index=chunk_index,
                content=chunk_content,
                hash=chunk_hash,
                start_pos=start_pos,
                end_pos=end_pos
            ))
            
            chunk_index += 1
        
        return chunks
    
    def _create_semantic_chunks(self, content: str) -> List[ChunkInfo]:
        """Create chunks based on semantic boundaries (AST-based)"""
        # This would use AST parsing to find semantic boundaries
        # For now, fallback to function-based chunking
        return self._create_function_based_chunks(content)
    
    def _create_adaptive_chunks(self, content: str) -> List[ChunkInfo]:
        """Create adaptive chunks based on content complexity"""
        chunks = []
        content_length = len(content)
        
        start = 0
        chunk_index = 0
        
        while start < content_length:
            # Calculate adaptive chunk size based on local complexity
            local_complexity = self._calculate_local_complexity(content, start)
            adaptive_size = int(self.chunk_size * (2 - local_complexity))  # Smaller chunks for complex code
            
            end = min(start + adaptive_size, content_length)
            
            # Extract chunk content
            chunk_content = content[start:end]
            chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()
            
            chunks.append(ChunkInfo(
                index=chunk_index,
                content=chunk_content,
                hash=chunk_hash,
                start_pos=start,
                end_pos=end
            ))
            
            start = end
            chunk_index += 1
        
        return chunks
    
    def _calculate_local_complexity(self, content: str, start_pos: int) -> float:
        """Calculate complexity of code around a position"""
        # Look at a window around the position
        window_size = min(1000, len(content) - start_pos)
        window = content[start_pos:start_pos + window_size]
        
        # Simple complexity metrics
        brace_count = window.count('{') + window.count('}')
        function_count = len(re.findall(r'function|=>', window))
        conditional_count = len(re.findall(r'\b(if|else|while|for|switch)\b', window))
        
        # Normalize complexity (0.0 to 1.0)
        complexity = (brace_count + function_count * 2 + conditional_count * 1.5) / len(window)
        return min(complexity * 100, 1.0)
    
    def _merge_chunk_results(self, chunk_results: List[Any]) -> Any:
        """Merge results from multiple chunks"""
        if not chunk_results:
            return None
        
        if len(chunk_results) == 1:
            return chunk_results[0]
        
        # Simple merge strategy - combine lists and sum numbers
        merged = {}
        
        for result in chunk_results:
            if isinstance(result, dict):
                for key, value in result.items():
                    if key not in merged:
                        merged[key] = value
                    elif isinstance(value, list) and isinstance(merged[key], list):
                        merged[key].extend(value)
                    elif isinstance(value, (int, float)) and isinstance(merged[key], (int, float)):
                        merged[key] += value
                    else:
                        # Keep the latest value for other types
                        merged[key] = value
        
        return merged
    
    async def _set_in_memory(self, key: str, entry: CacheEntry) -> None:
        """Set entry in memory cache with eviction if needed"""
        # Check if we need to evict entries
        while (self.current_memory_size + entry.size > self.max_memory_size and 
               len(self.memory_cache) > 0):
            await self._evict_memory_entry()
        
        # Add new entry
        self.memory_cache[key] = entry
        self.current_memory_size += entry.size
        
        # Update access tracking
        self._update_access_stats(key)
    
    async def _evict_memory_entry(self) -> None:
        """Evict an entry from memory cache based on strategy"""
        if not self.memory_cache:
            return
        
        if self.cache_strategy == CacheStrategy.LRU:
            # Remove least recently used
            key_to_remove = self.access_order[0]
        elif self.cache_strategy == CacheStrategy.LFU:
            # Remove least frequently used
            key_to_remove = min(self.access_frequency.keys(), 
                               key=lambda k: self.access_frequency[k])
        else:  # FIFO
            # Remove oldest entry
            key_to_remove = min(self.memory_cache.keys(), 
                               key=lambda k: self.memory_cache[k].created)
        
        await self._remove_from_memory(key_to_remove)
        self.stats['evictions'] += 1
    
    async def _remove_from_memory(self, key: str) -> None:
        """Remove entry from memory cache"""
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            self.current_memory_size -= entry.size
            del self.memory_cache[key]
            
            # Clean up access tracking
            if key in self.access_order:
                self.access_order.remove(key)
            if key in self.access_frequency:
                del self.access_frequency[key]
    
    def _update_access_stats(self, key: str) -> None:
        """Update access statistics for cache entry"""
        # Update access time
        if key in self.memory_cache:
            self.memory_cache[key].last_accessed = time.time()
            self.memory_cache[key].access_count += 1
        
        # Update LRU order
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        
        # Update LFU frequency
        self.access_frequency[key] = self.access_frequency.get(key, 0) + 1
    
    async def _get_from_disk(self, key: str) -> Optional[Any]:
        """Get data from disk cache"""
        cache_file = self.cache_dir / f"{key}.cache"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                return data
            except Exception:
                # Remove corrupted cache file
                cache_file.unlink(missing_ok=True)
        
        return None
    
    async def _set_on_disk(self, key: str, data: Any) -> None:
        """Set data in disk cache"""
        cache_file = self.cache_dir / f"{key}.cache"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception:
            # Handle disk write errors gracefully
            pass
    
    async def clear(self) -> None:
        """Clear all cached data"""
        # Clear memory cache
        self.memory_cache.clear()
        self.access_order.clear()
        self.access_frequency.clear()
        self.current_memory_size = 0
        
        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink(missing_ok=True)
        
        # Reset statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'chunks_processed': 0,
            'chunks_cached': 0
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': hit_rate,
            'memory_entries': len(self.memory_cache),
            'memory_size': self.current_memory_size,
            'memory_utilization': self.current_memory_size / self.max_memory_size
        }
    
    async def invalidate(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        import fnmatch
        
        invalidated = 0
        
        # Invalidate memory cache
        keys_to_remove = [key for key in self.memory_cache.keys() 
                         if fnmatch.fnmatch(key, pattern)]
        
        for key in keys_to_remove:
            await self._remove_from_memory(key)
            invalidated += 1
        
        # Invalidate disk cache
        for cache_file in self.cache_dir.glob("*.cache"):
            key = cache_file.stem
            if fnmatch.fnmatch(key, pattern):
                cache_file.unlink(missing_ok=True)
                invalidated += 1
        
        return invalidated
