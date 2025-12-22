#!/usr/bin/env python3
"""
Bundle Analysis Engine for Packer-InfoFinder v2.0
Advanced bundle composition analysis and size optimization tools

This module provides comprehensive bundle analysis using:
- wakaru: Modern webpack decompiler for bundle analysis
- webpack-bundle-analyzer: Bundle size analysis and optimization
- jscpd: Code duplication detection for size optimization
- recast: AST transformation for code understanding
"""

import asyncio
import subprocess
import tempfile
import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib


@dataclass
class BundleModule:
    """Information about a module in the bundle"""
    id: str
    name: str
    size_bytes: int
    gzipped_size: Optional[int]
    path: str
    chunks: List[str]
    dependencies: List[str]
    exports: List[str]
    imports: List[str]
    is_entry: bool = False
    is_vendor: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BundleChunk:
    """Information about a chunk in the bundle"""
    id: str
    name: str
    size_bytes: int
    modules: List[str]
    entry_points: List[str]
    is_initial: bool = False
    is_async: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BundleAnalysisResult:
    """Complete bundle analysis results"""
    total_size: int
    gzipped_size: Optional[int]
    modules: List[BundleModule]
    chunks: List[BundleChunk]
    dependencies: Dict[str, int]  # dependency -> size
    duplicates: List[Dict[str, Any]]
    optimization_opportunities: List[Dict[str, Any]]
    size_breakdown: Dict[str, int]
    analysis_time: float


class WakaruAnalyzer:
    """Wakaru webpack decompiler integration"""
    
    def __init__(self):
        self.tool_name = "wakaru"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if wakaru is available"""
        try:
            result = subprocess.run(['npm', 'list', 'wakaru'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def decompile_bundle(self, code: str, file_path: str) -> Dict[str, Any]:
        """Decompile webpack bundle using wakaru"""
        if not self.available:
            return self._fallback_bundle_analysis(code)
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run wakaru decompiler
            cmd = ['npx', 'wakaru', tmp_file_path, '--output-format', 'json']
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return self._fallback_bundle_analysis(code)
                
        except Exception as e:
            return self._fallback_bundle_analysis(code)
        
        finally:
            try:
                os.unlink(tmp_file_path)
            except:
                pass
    
    def _fallback_bundle_analysis(self, code: str) -> Dict[str, Any]:
        """Fallback bundle analysis when wakaru is not available"""
        # Basic webpack pattern detection
        modules = self._extract_webpack_modules(code)
        chunks = self._extract_webpack_chunks(code)
        
        return {
            'modules': modules,
            'chunks': chunks,
            'webpack_detected': 'webpackJsonp' in code or '__webpack_require__' in code,
            'fallback_analysis': True
        }
    
    def _extract_webpack_modules(self, code: str) -> List[Dict[str, Any]]:
        """Extract webpack modules using regex patterns"""
        modules = []
        
        # Pattern for webpack module definitions
        module_pattern = r'(?:webpackJsonp|__webpack_require__\.cache)\[(\d+)\]\s*=\s*function\s*\([^)]*\)\s*\{'
        
        for match in re.finditer(module_pattern, code):
            module_id = match.group(1)
            start_pos = match.start()
            
            # Extract module content
            module_content = self._extract_module_content(code, start_pos)
            
            modules.append({
                'id': module_id,
                'size': len(module_content),
                'content_preview': module_content[:200] + '...' if len(module_content) > 200 else module_content
            })
        
        return modules
    
    def _extract_webpack_chunks(self, code: str) -> List[Dict[str, Any]]:
        """Extract webpack chunks using regex patterns"""
        chunks = []
        
        # Pattern for chunk definitions
        chunk_pattern = r'webpackJsonp\(\[([^\]]+)\]'
        
        for match in re.finditer(chunk_pattern, code):
            chunk_ids = match.group(1).split(',')
            chunks.append({
                'ids': [id.strip() for id in chunk_ids],
                'size_estimate': 1000  # Rough estimate
            })
        
        return chunks
    
    def _extract_module_content(self, code: str, start_pos: int) -> str:
        """Extract module content with brace matching"""
        brace_count = 0
        i = start_pos
        
        # Find opening brace
        while i < len(code) and code[i] != '{':
            i += 1
        
        if i >= len(code):
            return ""
        
        start_content = i
        brace_count = 1
        i += 1
        
        # Match braces
        while i < len(code) and brace_count > 0:
            if code[i] == '{':
                brace_count += 1
            elif code[i] == '}':
                brace_count -= 1
            i += 1
        
        return code[start_content:i] if brace_count == 0 else code[start_content:start_content + 1000]


class WebpackBundleAnalyzer:
    """webpack-bundle-analyzer integration"""
    
    def __init__(self):
        self.tool_name = "webpack-bundle-analyzer"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if webpack-bundle-analyzer is available"""
        try:
            result = subprocess.run(['npm', 'list', 'webpack-bundle-analyzer'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def analyze_bundle_size(self, code: str, file_path: str) -> Dict[str, Any]:
        """Analyze bundle size using webpack-bundle-analyzer"""
        if not self.available:
            return self._fallback_size_analysis(code)
        
        try:
            # Create temporary webpack stats file
            stats_data = self._create_webpack_stats(code, file_path)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as stats_file:
                json.dump(stats_data, stats_file)
                stats_file_path = stats_file.name
            
            # Run webpack-bundle-analyzer
            cmd = ['npx', 'webpack-bundle-analyzer', stats_file_path, '--mode', 'json']
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return self._fallback_size_analysis(code)
                
        except Exception as e:
            return self._fallback_size_analysis(code)
        
        finally:
            try:
                os.unlink(stats_file_path)
            except:
                pass
    
    def _create_webpack_stats(self, code: str, file_path: str) -> Dict[str, Any]:
        """Create webpack stats data for analysis"""
        return {
            "version": "5.0.0",
            "hash": hashlib.md5(code.encode()).hexdigest()[:8],
            "time": 1000,
            "builtAt": 1640995200000,
            "publicPath": "",
            "outputPath": "/",
            "assetsByChunkName": {
                "main": [file_path]
            },
            "assets": [
                {
                    "name": file_path,
                    "size": len(code.encode('utf-8')),
                    "chunks": [0],
                    "chunkNames": ["main"],
                    "emitted": True
                }
            ],
            "chunks": [
                {
                    "id": 0,
                    "rendered": True,
                    "initial": True,
                    "entry": True,
                    "size": len(code.encode('utf-8')),
                    "names": ["main"],
                    "files": [file_path],
                    "modules": self._extract_modules_for_stats(code)
                }
            ],
            "modules": self._extract_modules_for_stats(code)
        }
    
    def _extract_modules_for_stats(self, code: str) -> List[Dict[str, Any]]:
        """Extract modules for webpack stats"""
        modules = []
        
        # Simple module extraction based on common patterns
        lines = code.split('\n')
        current_module = None
        module_id = 0
        
        for i, line in enumerate(lines):
            # Detect potential module boundaries
            if any(pattern in line for pattern in ['function(', 'module.exports', 'exports.', 'require(']):
                if current_module:
                    modules.append(current_module)
                
                current_module = {
                    "id": module_id,
                    "identifier": f"module_{module_id}",
                    "name": f"./module_{module_id}.js",
                    "size": 0,
                    "chunks": [0],
                    "built": True,
                    "optional": False,
                    "prefetched": False,
                    "cacheable": True
                }
                module_id += 1
            
            if current_module:
                current_module["size"] += len(line.encode('utf-8'))
        
        # Add final module
        if current_module:
            modules.append(current_module)
        
        return modules
    
    def _fallback_size_analysis(self, code: str) -> Dict[str, Any]:
        """Fallback size analysis"""
        total_size = len(code.encode('utf-8'))
        
        return {
            "total_size": total_size,
            "gzipped_estimate": int(total_size * 0.3),  # Rough gzip estimate
            "modules_count": code.count('function(') + code.count('module.exports'),
            "fallback_analysis": True
        }


class JSCPDAnalyzer:
    """jscpd code duplication detection integration"""
    
    def __init__(self):
        self.tool_name = "jscpd"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if jscpd is available"""
        try:
            result = subprocess.run(['npx', 'jscpd', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def detect_duplicates(self, code: str, file_path: str) -> Dict[str, Any]:
        """Detect code duplicates using jscpd"""
        if not self.available:
            return self._fallback_duplicate_detection(code)
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run jscpd
            cmd = ['npx', 'jscpd', tmp_file_path, '--format', 'json', '--min-lines', '5', '--min-tokens', '50']
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return self._fallback_duplicate_detection(code)
                
        except Exception as e:
            return self._fallback_duplicate_detection(code)
        
        finally:
            try:
                os.unlink(tmp_file_path)
            except:
                pass
    
    def _fallback_duplicate_detection(self, code: str) -> Dict[str, Any]:
        """Fallback duplicate detection using simple hashing"""
        duplicates = []
        lines = code.split('\n')
        
        # Group lines by hash to find duplicates
        line_hashes = {}
        for i, line in enumerate(lines):
            if len(line.strip()) > 20:  # Only consider substantial lines
                line_hash = hashlib.md5(line.strip().encode()).hexdigest()
                if line_hash in line_hashes:
                    line_hashes[line_hash].append((i, line.strip()))
                else:
                    line_hashes[line_hash] = [(i, line.strip())]
        
        # Find actual duplicates
        for line_hash, occurrences in line_hashes.items():
            if len(occurrences) > 1:
                duplicates.append({
                    'lines': [occ[0] for occ in occurrences],
                    'content': occurrences[0][1],
                    'count': len(occurrences),
                    'estimated_savings': len(occurrences[0][1]) * (len(occurrences) - 1)
                })
        
        total_duplicates = len(duplicates)
        total_savings = sum(dup['estimated_savings'] for dup in duplicates)
        
        return {
            'duplicates': duplicates,
            'statistics': {
                'total': total_duplicates,
                'totalLines': len(lines),
                'percentage': (total_duplicates / len(lines)) * 100 if lines else 0,
                'estimatedSavings': total_savings
            },
            'fallback_analysis': True
        }


class BundleAnalysisEngine:
    """Main bundle analysis engine coordinating all bundle analysis tools"""
    
    def __init__(self):
        self.wakaru_analyzer = WakaruAnalyzer()
        self.webpack_analyzer = WebpackBundleAnalyzer()
        self.jscpd_analyzer = JSCPDAnalyzer()
    
    async def analyze_bundle(self, code: str, file_path: str) -> BundleAnalysisResult:
        """Perform comprehensive bundle analysis"""
        import time
        start_time = time.time()
        
        # Step 1: Decompile bundle structure using wakaru
        wakaru_result = await self.wakaru_analyzer.decompile_bundle(code, file_path)
        
        # Step 2: Analyze bundle size using webpack-bundle-analyzer
        size_result = await self.webpack_analyzer.analyze_bundle_size(code, file_path)
        
        # Step 3: Detect code duplicates using jscpd
        duplicate_result = await self.jscpd_analyzer.detect_duplicates(code, file_path)
        
        # Step 4: Process and combine results
        modules = self._process_modules(wakaru_result, size_result)
        chunks = self._process_chunks(wakaru_result, size_result)
        dependencies = self._extract_dependencies(wakaru_result)
        duplicates = self._process_duplicates(duplicate_result)
        optimizations = self._identify_optimizations(modules, duplicates, size_result)
        size_breakdown = self._calculate_size_breakdown(modules, size_result)
        
        analysis_time = time.time() - start_time
        
        return BundleAnalysisResult(
            total_size=len(code.encode('utf-8')),
            gzipped_size=size_result.get('gzipped_estimate'),
            modules=modules,
            chunks=chunks,
            dependencies=dependencies,
            duplicates=duplicates,
            optimization_opportunities=optimizations,
            size_breakdown=size_breakdown,
            analysis_time=analysis_time
        )
    
    def _process_modules(self, wakaru_result: Dict[str, Any], size_result: Dict[str, Any]) -> List[BundleModule]:
        """Process module information from analysis results"""
        modules = []
        
        wakaru_modules = wakaru_result.get('modules', [])
        size_modules = size_result.get('modules', [])
        
        # Combine information from both analyzers
        for i, wakaru_mod in enumerate(wakaru_modules):
            size_mod = size_modules[i] if i < len(size_modules) else {}
            
            module = BundleModule(
                id=str(wakaru_mod.get('id', i)),
                name=wakaru_mod.get('name', f'module_{i}'),
                size_bytes=wakaru_mod.get('size', size_mod.get('size', 0)),
                gzipped_size=None,  # Would need additional analysis
                path=wakaru_mod.get('path', f'./module_{i}.js'),
                chunks=[str(wakaru_mod.get('chunk', 0))],
                dependencies=wakaru_mod.get('dependencies', []),
                exports=wakaru_mod.get('exports', []),
                imports=wakaru_mod.get('imports', []),
                is_entry=wakaru_mod.get('isEntry', False),
                is_vendor='node_modules' in wakaru_mod.get('path', '')
            )
            modules.append(module)
        
        return modules
    
    def _process_chunks(self, wakaru_result: Dict[str, Any], size_result: Dict[str, Any]) -> List[BundleChunk]:
        """Process chunk information from analysis results"""
        chunks = []
        
        wakaru_chunks = wakaru_result.get('chunks', [])
        size_chunks = size_result.get('chunks', [])
        
        for i, wakaru_chunk in enumerate(wakaru_chunks):
            size_chunk = size_chunks[i] if i < len(size_chunks) else {}
            
            chunk = BundleChunk(
                id=str(wakaru_chunk.get('id', i)),
                name=wakaru_chunk.get('name', f'chunk_{i}'),
                size_bytes=wakaru_chunk.get('size', size_chunk.get('size', 0)),
                modules=wakaru_chunk.get('modules', []),
                entry_points=wakaru_chunk.get('entryPoints', []),
                is_initial=wakaru_chunk.get('initial', True),
                is_async=wakaru_chunk.get('async', False)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _extract_dependencies(self, wakaru_result: Dict[str, Any]) -> Dict[str, int]:
        """Extract dependency information"""
        dependencies = {}
        
        modules = wakaru_result.get('modules', [])
        for module in modules:
            for dep in module.get('dependencies', []):
                if dep in dependencies:
                    dependencies[dep] += module.get('size', 0)
                else:
                    dependencies[dep] = module.get('size', 0)
        
        return dependencies
    
    def _process_duplicates(self, duplicate_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process duplicate detection results"""
        duplicates = duplicate_result.get('duplicates', [])
        
        processed_duplicates = []
        for dup in duplicates:
            processed_duplicates.append({
                'type': 'code_duplication',
                'lines': dup.get('lines', []),
                'content_preview': dup.get('content', '')[:100] + '...',
                'occurrences': dup.get('count', 0),
                'estimated_savings': dup.get('estimated_savings', 0),
                'priority': 'high' if dup.get('estimated_savings', 0) > 1000 else 'medium'
            })
        
        return processed_duplicates
    
    def _identify_optimizations(self, modules: List[BundleModule], duplicates: List[Dict[str, Any]], 
                               size_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify optimization opportunities"""
        optimizations = []
        
        # Large module optimization
        large_modules = [m for m in modules if m.size_bytes > 100000]  # > 100KB
        if large_modules:
            total_savings = sum(m.size_bytes * 0.2 for m in large_modules)  # Estimate 20% reduction
            optimizations.append({
                'type': 'large_modules',
                'count': len(large_modules),
                'estimated_savings': int(total_savings),
                'priority': 'high',
                'description': f'Found {len(large_modules)} large modules that could be optimized or split'
            })
        
        # Vendor bundle optimization
        vendor_modules = [m for m in modules if m.is_vendor]
        if vendor_modules:
            vendor_size = sum(m.size_bytes for m in vendor_modules)
            optimizations.append({
                'type': 'vendor_bundling',
                'count': len(vendor_modules),
                'estimated_savings': int(vendor_size * 0.1),  # Estimate 10% reduction
                'priority': 'medium',
                'description': f'Vendor modules could be better optimized or cached separately'
            })
        
        # Duplicate code optimization
        if duplicates:
            total_duplicate_savings = sum(dup['estimated_savings'] for dup in duplicates)
            optimizations.append({
                'type': 'code_deduplication',
                'count': len(duplicates),
                'estimated_savings': total_duplicate_savings,
                'priority': 'high',
                'description': f'Found {len(duplicates)} instances of duplicate code'
            })
        
        # Tree shaking opportunities
        unused_exports = self._detect_unused_exports(modules)
        if unused_exports:
            optimizations.append({
                'type': 'tree_shaking',
                'count': len(unused_exports),
                'estimated_savings': len(unused_exports) * 500,  # Rough estimate
                'priority': 'medium',
                'description': f'Found {len(unused_exports)} potentially unused exports'
            })
        
        return optimizations
    
    def _detect_unused_exports(self, modules: List[BundleModule]) -> List[str]:
        """Detect potentially unused exports (simplified)"""
        all_exports = set()
        all_imports = set()
        
        for module in modules:
            all_exports.update(module.exports)
            all_imports.update(module.imports)
        
        # Exports that are never imported (simplified detection)
        unused_exports = list(all_exports - all_imports)
        return unused_exports
    
    def _calculate_size_breakdown(self, modules: List[BundleModule], size_result: Dict[str, Any]) -> Dict[str, int]:
        """Calculate size breakdown by category"""
        breakdown = {
            'application_code': 0,
            'vendor_libraries': 0,
            'polyfills': 0,
            'other': 0
        }
        
        for module in modules:
            if module.is_vendor:
                breakdown['vendor_libraries'] += module.size_bytes
            elif 'polyfill' in module.name.lower():
                breakdown['polyfills'] += module.size_bytes
            elif module.path.startswith('./src') or module.path.startswith('./app'):
                breakdown['application_code'] += module.size_bytes
            else:
                breakdown['other'] += module.size_bytes
        
        return breakdown


# Example usage and testing
async def main():
    """Example usage of the bundle analysis engine"""
    
    # Sample webpack bundle code (simplified)
    sample_bundle = '''
    (function(modules) {
        var installedModules = {};
        
        function __webpack_require__(moduleId) {
            if(installedModules[moduleId]) {
                return installedModules[moduleId].exports;
            }
            var module = installedModules[moduleId] = {
                i: moduleId,
                l: false,
                exports: {}
            };
            
            modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
            module.l = true;
            return module.exports;
        }
        
        return __webpack_require__(0);
    })([
        function(module, exports, __webpack_require__) {
            // Module 0 - Entry point
            const utils = __webpack_require__(1);
            const lodash = __webpack_require__(2);
            
            function main() {
                console.log('Application started');
                utils.initialize();
                return lodash.map([1, 2, 3], x => x * 2);
            }
            
            module.exports = main;
        },
        function(module, exports) {
            // Module 1 - Utils
            function initialize() {
                console.log('Utils initialized');
            }
            
            function helper() {
                return 'helper function';
            }
            
            module.exports = { initialize, helper };
        },
        function(module, exports) {
            // Module 2 - Lodash (simplified)
            function map(array, iteratee) {
                const result = [];
                for (let i = 0; i < array.length; i++) {
                    result.push(iteratee(array[i]));
                }
                return result;
            }
            
            module.exports = { map };
        }
    ]);
    ''' * 1000  # Repeat to make it larger
    
    # Initialize bundle analysis engine
    bundle_engine = BundleAnalysisEngine()
    
    # Perform analysis
    print("🔍 Running comprehensive bundle analysis...")
    result = await bundle_engine.analyze_bundle(sample_bundle, "bundle.js")
    
    # Display results
    print(f"\n📊 Bundle Analysis Results:")
    print(f"   • Total size: {result.total_size:,} bytes ({result.total_size / (1024*1024):.1f} MB)")
    if result.gzipped_size:
        print(f"   • Gzipped size: {result.gzipped_size:,} bytes")
    print(f"   • Modules: {len(result.modules)}")
    print(f"   • Chunks: {len(result.chunks)}")
    print(f"   • Analysis time: {result.analysis_time:.2f}s")
    
    print(f"\n📈 Size Breakdown:")
    for category, size in result.size_breakdown.items():
        if size > 0:
            percentage = (size / result.total_size) * 100
            print(f"   • {category.replace('_', ' ').title()}: {size:,} bytes ({percentage:.1f}%)")
    
    print(f"\n🔍 Top Dependencies:")
    sorted_deps = sorted(result.dependencies.items(), key=lambda x: x[1], reverse=True)
    for dep, size in sorted_deps[:5]:
        print(f"   • {dep}: {size:,} bytes")
    
    print(f"\n🎯 Optimization Opportunities:")
    for opt in result.optimization_opportunities:
        print(f"   • {opt['type'].replace('_', ' ').title()}: {opt['description']}")
        print(f"     Priority: {opt['priority']}, Estimated savings: {opt['estimated_savings']:,} bytes")
    
    if result.duplicates:
        print(f"\n🔄 Code Duplicates Found: {len(result.duplicates)}")
        for dup in result.duplicates[:3]:  # Show first 3
            print(f"   • {dup['occurrences']} occurrences, saves {dup['estimated_savings']} bytes")


if __name__ == "__main__":
    asyncio.run(main())
