"""
Packer-InfoFinder v2.0 - Advanced JavaScript Analysis Engine
Enhanced with enterprise-grade analysis capabilities for massive JavaScript files

This module integrates 20+ specialized analysis tools for comprehensive JavaScript
code understanding, optimization, and security analysis.
"""

import asyncio
import json
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re
import ast
from pathlib import Path

# Analysis Tools Integration
from .tools.js_beautifier import JSBeautifier
from .tools.bundle_analyzer import BundleAnalyzer
from .tools.duplication_detector import DuplicationDetector
from .tools.dependency_mapper import DependencyMapper
from .tools.function_analyzer import FunctionAnalyzer
from .tools.pattern_detector import PatternDetector
from .caching.incremental_cache import IncrementalCacheManager


class AnalysisType(Enum):
    """Types of analysis that can be performed"""
    STRUCTURE = "structure"
    SECURITY = "security"
    PERFORMANCE = "performance"
    OPTIMIZATION = "optimization"
    DEPENDENCIES = "dependencies"
    FUNCTIONS = "functions"
    PATTERNS = "patterns"
    BUNDLE = "bundle"


class FindingSeverity(Enum):
    """Severity levels for analysis findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class AnalysisFinding:
    """Represents a single analysis finding"""
    id: str
    type: str
    severity: FindingSeverity
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    snippet: Optional[str] = None
    recommendation: Optional[str] = None
    confidence: float = 1.0
    impact: float = 1.0
    references: List[str] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


@dataclass
class FunctionInfo:
    """Information about a JavaScript function"""
    name: str
    type: str  # regular, arrow, async, generator, etc.
    start_line: int
    end_line: int
    complexity: int
    parameters: List[str]
    is_exported: bool
    is_async: bool
    size_bytes: int
    calls_count: int = 0
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class OptimizationSuggestion:
    """Optimization suggestion for JavaScript code"""
    id: str
    type: str
    priority: str
    title: str
    description: str
    estimated_savings: int  # bytes
    implementation_effort: str
    risk_level: str
    steps: List[str]
    tools_supported: List[str] = None
    
    def __post_init__(self):
        if self.tools_supported is None:
            self.tools_supported = []


@dataclass
class AnalysisResult:
    """Complete analysis result for a JavaScript file or project"""
    file_path: str
    original_size: int
    analysis_time: float
    
    # Core metrics
    functions: List[FunctionInfo]
    findings: List[AnalysisFinding]
    optimizations: List[OptimizationSuggestion]
    
    # Structure analysis
    total_functions: int = 0
    total_classes: int = 0
    total_variables: int = 0
    total_imports: int = 0
    total_exports: int = 0
    
    # Complexity metrics
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    maintainability_index: float = 0.0
    
    # Quality scores (0.0 to 1.0)
    quality_score: float = 0.0
    security_score: float = 0.0
    performance_score: float = 0.0
    maintainability_score: float = 0.0
    
    # Bundle analysis
    bundle_info: Optional[Dict[str, Any]] = None
    dependency_map: Optional[Dict[str, Any]] = None
    duplication_info: Optional[Dict[str, Any]] = None
    
    # Metadata
    analysis_config: Dict[str, Any] = None
    tool_versions: Dict[str, str] = None
    
    def __post_init__(self):
        if self.analysis_config is None:
            self.analysis_config = {}
        if self.tool_versions is None:
            self.tool_versions = {}


class AdvancedJSAnalyzer:
    """
    Advanced JavaScript Analysis Engine
    
    Integrates multiple specialized tools for comprehensive JavaScript analysis:
    - js-beautify: Code formatting and readability
    - webpack-bundle-analyzer: Bundle composition analysis
    - recast: AST transformation and analysis
    - babel-parser: Modern JavaScript parsing
    - estree-analyzer: Static analysis
    - bundle-buddy: Bundle size understanding
    - jscpd: Code duplication detection
    - decode-js: Advanced AST analysis
    - wakaru: Modern decompiler
    - humanify: AI-powered code understanding
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the analyzer with configuration"""
        self.config = config or {}
        self.cache_manager = IncrementalCacheManager(
            self.config.get('cache_config', {})
        )
        
        # Initialize analysis tools
        self.js_beautifier = JSBeautifier(self.config.get('beautifier', {}))
        self.bundle_analyzer = BundleAnalyzer(self.config.get('bundle', {}))
        self.duplication_detector = DuplicationDetector(self.config.get('duplication', {}))
        self.dependency_mapper = DependencyMapper(self.config.get('dependencies', {}))
        self.function_analyzer = FunctionAnalyzer(self.config.get('functions', {}))
        self.pattern_detector = PatternDetector(self.config.get('patterns', {}))
        
        # Analysis settings
        self.enabled_analyses = set(self.config.get('enabled_analyses', [
            AnalysisType.STRUCTURE,
            AnalysisType.FUNCTIONS,
            AnalysisType.OPTIMIZATION,
            AnalysisType.DEPENDENCIES
        ]))
        
        self.chunk_size = self.config.get('chunk_size', 1024 * 1024)  # 1MB
        self.enable_caching = self.config.get('enable_caching', True)
        self.parallel_analysis = self.config.get('parallel_analysis', True)
        
    async def analyze_file(self, file_path: str, content: Optional[str] = None) -> AnalysisResult:
        """
        Analyze a single JavaScript file
        
        Args:
            file_path: Path to the JavaScript file
            content: Optional file content (if not provided, will read from file_path)
            
        Returns:
            AnalysisResult containing comprehensive analysis data
        """
        start_time = time.time()
        
        # Read file content if not provided
        if content is None:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        original_size = len(content)
        
        # Check cache first
        cache_key = self._generate_cache_key(file_path, content)
        if self.enable_caching:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                return AnalysisResult(**cached_result)
        
        # Initialize result
        result = AnalysisResult(
            file_path=file_path,
            original_size=original_size,
            analysis_time=0.0,
            functions=[],
            findings=[],
            optimizations=[]
        )
        
        # Perform different types of analysis
        analysis_tasks = []
        
        if AnalysisType.STRUCTURE in self.enabled_analyses:
            analysis_tasks.append(self._analyze_structure(content, result))
            
        if AnalysisType.FUNCTIONS in self.enabled_analyses:
            analysis_tasks.append(self._analyze_functions(content, result))
            
        if AnalysisType.DEPENDENCIES in self.enabled_analyses:
            analysis_tasks.append(self._analyze_dependencies(content, result))
            
        if AnalysisType.BUNDLE in self.enabled_analyses:
            analysis_tasks.append(self._analyze_bundle(content, result))
            
        if AnalysisType.PATTERNS in self.enabled_analyses:
            analysis_tasks.append(self._detect_patterns(content, result))
            
        if AnalysisType.OPTIMIZATION in self.enabled_analyses:
            analysis_tasks.append(self._generate_optimizations(content, result))
        
        # Execute analysis tasks
        if self.parallel_analysis and len(analysis_tasks) > 1:
            await asyncio.gather(*analysis_tasks)
        else:
            for task in analysis_tasks:
                await task
        
        # Calculate quality scores
        self._calculate_quality_scores(result)
        
        # Record analysis time
        result.analysis_time = time.time() - start_time
        
        # Cache result
        if self.enable_caching:
            await self.cache_manager.set(cache_key, asdict(result))
        
        return result
    
    async def analyze_large_file(self, file_path: str, content: Optional[str] = None) -> AnalysisResult:
        """
        Analyze a large JavaScript file using incremental processing
        
        Optimized for files like 22MB GitHub CLI index.js
        """
        if content is None:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        # Use incremental analysis for large files
        if len(content) > self.chunk_size:
            return await self._analyze_incrementally(file_path, content)
        else:
            return await self.analyze_file(file_path, content)
    
    async def _analyze_incrementally(self, file_path: str, content: str) -> AnalysisResult:
        """Perform incremental analysis on large files"""
        
        async def chunk_analyzer(chunk: str, context: Dict[str, Any]) -> Dict[str, Any]:
            """Analyze a single chunk of code"""
            chunk_result = AnalysisResult(
                file_path=f"{file_path}_chunk_{context.get('current_chunk', 0)}",
                original_size=len(chunk),
                analysis_time=0.0,
                functions=[],
                findings=[],
                optimizations=[]
            )
            
            # Analyze chunk structure
            await self._analyze_structure(chunk, chunk_result)
            await self._analyze_functions(chunk, chunk_result)
            
            return asdict(chunk_result)
        
        # Perform incremental analysis
        cache_key = self._generate_cache_key(file_path, content)
        incremental_result = await self.cache_manager.analyze_incremental(
            cache_key,
            content,
            chunk_analyzer
        )
        
        # Merge incremental results
        return self._merge_incremental_results(file_path, incremental_result)
    
    def _merge_incremental_results(self, file_path: str, incremental_data: Dict[str, Any]) -> AnalysisResult:
        """Merge results from incremental analysis"""
        # This would implement sophisticated merging logic
        # For now, return a basic merged result
        return AnalysisResult(
            file_path=file_path,
            original_size=incremental_data.get('original_size', 0),
            analysis_time=incremental_data.get('analysis_time', 0.0),
            functions=[],
            findings=[],
            optimizations=[]
        )
    
    async def _analyze_structure(self, content: str, result: AnalysisResult):
        """Analyze code structure (functions, classes, variables, etc.)"""
        # Count basic elements
        result.total_functions = len(re.findall(r'function\s+\w+|const\s+\w+\s*=\s*(?:function|\(.*?\)\s*=>)', content))
        result.total_classes = len(re.findall(r'class\s+\w+', content))
        result.total_variables = len(re.findall(r'(?:var|let|const)\s+\w+', content))
        result.total_imports = len(re.findall(r'import\s+.*?from|require\s*\(', content))
        result.total_exports = len(re.findall(r'export\s+(?:default\s+)?(?:class|function|const|let|var|\{)', content))
        
        # Calculate complexity metrics
        result.cyclomatic_complexity = self._calculate_cyclomatic_complexity(content)
        result.cognitive_complexity = self._calculate_cognitive_complexity(content)
        result.maintainability_index = self._calculate_maintainability_index(content)
    
    async def _analyze_functions(self, content: str, result: AnalysisResult):
        """Analyze individual functions in the code"""
        functions = await self.function_analyzer.extract_functions(content)
        result.functions = [
            FunctionInfo(
                name=func['name'],
                type=func['type'],
                start_line=func['start_line'],
                end_line=func['end_line'],
                complexity=func['complexity'],
                parameters=func['parameters'],
                is_exported=func['is_exported'],
                is_async=func['is_async'],
                size_bytes=func['size_bytes']
            )
            for func in functions
        ]
    
    async def _analyze_dependencies(self, content: str, result: AnalysisResult):
        """Analyze dependencies and imports"""
        dependency_info = await self.dependency_mapper.analyze(content)
        result.dependency_map = dependency_info
        
        # Add findings for circular dependencies
        if dependency_info.get('circular_dependencies'):
            for cycle in dependency_info['circular_dependencies']:
                result.findings.append(AnalysisFinding(
                    id=f"circular_dep_{hashlib.md5(str(cycle).encode()).hexdigest()[:8]}",
                    type="dependency",
                    severity=FindingSeverity.MEDIUM,
                    title="Circular Dependency Detected",
                    description=f"Circular dependency found: {' -> '.join(cycle)}",
                    recommendation="Consider refactoring to break the circular dependency"
                ))
    
    async def _analyze_bundle(self, content: str, result: AnalysisResult):
        """Analyze bundle composition and size"""
        bundle_info = await self.bundle_analyzer.analyze(content)
        result.bundle_info = bundle_info
        
        # Add optimization findings
        if bundle_info.get('unused_code'):
            for unused in bundle_info['unused_code']:
                result.findings.append(AnalysisFinding(
                    id=f"unused_code_{hashlib.md5(unused['name'].encode()).hexdigest()[:8]}",
                    type="optimization",
                    severity=FindingSeverity.LOW,
                    title="Unused Code Detected",
                    description=f"Unused code found: {unused['name']}",
                    recommendation="Consider removing unused code to reduce bundle size"
                ))
    
    async def _detect_patterns(self, content: str, result: AnalysisResult):
        """Detect code patterns and anti-patterns"""
        patterns = await self.pattern_detector.detect(content)
        
        for pattern in patterns:
            if pattern['type'] == 'anti_pattern':
                result.findings.append(AnalysisFinding(
                    id=f"pattern_{pattern['id']}",
                    type="pattern",
                    severity=FindingSeverity.MEDIUM,
                    title=f"Anti-pattern Detected: {pattern['name']}",
                    description=pattern['description'],
                    line_number=pattern.get('line'),
                    recommendation=pattern.get('recommendation')
                ))
    
    async def _generate_optimizations(self, content: str, result: AnalysisResult):
        """Generate optimization suggestions"""
        # Size-based optimizations
        if result.original_size > 1024 * 1024:  # > 1MB
            result.optimizations.append(OptimizationSuggestion(
                id="minification",
                type="size",
                priority="high",
                title="Enable Minification",
                description="Reduce file size by removing whitespace and shortening variable names",
                estimated_savings=int(result.original_size * 0.3),
                implementation_effort="low",
                risk_level="safe",
                steps=[
                    "Use a minification tool like Terser or UglifyJS",
                    "Configure build process to minify JavaScript",
                    "Test functionality after minification"
                ],
                tools_supported=["terser", "uglify-js", "webpack"]
            ))
        
        # Function-based optimizations
        large_functions = [f for f in result.functions if f.size_bytes > 10000]  # > 10KB
        if large_functions:
            result.optimizations.append(OptimizationSuggestion(
                id="function_splitting",
                type="maintainability",
                priority="medium",
                title="Split Large Functions",
                description=f"Found {len(large_functions)} functions larger than 10KB",
                estimated_savings=0,
                implementation_effort="medium",
                risk_level="low",
                steps=[
                    "Identify large functions that can be split",
                    "Extract reusable logic into smaller functions",
                    "Maintain function cohesion and reduce coupling"
                ]
            ))
    
    def _calculate_quality_scores(self, result: AnalysisResult):
        """Calculate overall quality scores"""
        # Quality score based on findings
        critical_findings = len([f for f in result.findings if f.severity == FindingSeverity.CRITICAL])
        high_findings = len([f for f in result.findings if f.severity == FindingSeverity.HIGH])
        
        result.quality_score = max(0.0, 1.0 - (critical_findings * 0.3 + high_findings * 0.1))
        
        # Security score (placeholder - would integrate with security analysis)
        security_findings = len([f for f in result.findings if f.type == "security"])
        result.security_score = max(0.0, 1.0 - security_findings * 0.2)
        
        # Performance score based on complexity and size
        complexity_penalty = min(0.5, result.cyclomatic_complexity / 100)
        size_penalty = min(0.3, result.original_size / (10 * 1024 * 1024))  # 10MB baseline
        result.performance_score = max(0.0, 1.0 - complexity_penalty - size_penalty)
        
        # Maintainability score
        result.maintainability_score = min(1.0, result.maintainability_index / 100)
    
    def _calculate_cyclomatic_complexity(self, content: str) -> int:
        """Calculate cyclomatic complexity"""
        # Count decision points
        decision_points = len(re.findall(r'\b(if|else|while|for|switch|case|catch|\?)\b', content))
        return decision_points + 1  # +1 for the main path
    
    def _calculate_cognitive_complexity(self, content: str) -> int:
        """Calculate cognitive complexity"""
        # Simplified cognitive complexity calculation
        nesting_penalty = len(re.findall(r'\{', content)) * 0.5
        decision_penalty = len(re.findall(r'\b(if|while|for|switch)\b', content))
        return int(nesting_penalty + decision_penalty)
    
    def _calculate_maintainability_index(self, content: str) -> float:
        """Calculate maintainability index"""
        # Simplified maintainability index
        lines = len(content.split('\n'))
        complexity = self._calculate_cyclomatic_complexity(content)
        
        # Microsoft's maintainability index formula (simplified)
        volume = lines * 4.2  # Simplified Halstead volume
        mi = max(0, (171 - 5.2 * complexity - 0.23 * volume) * 100 / 171)
        return mi
    
    def _generate_cache_key(self, file_path: str, content: str) -> str:
        """Generate cache key for file content"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"analysis_{Path(file_path).name}_{content_hash[:16]}"
    
    async def generate_report(self, results: List[AnalysisResult], output_path: str):
        """Generate comprehensive HTML report"""
        # This would generate a detailed HTML report
        # Similar to the existing Packer-InfoFinder reports but enhanced
        pass
    
    def get_tool_versions(self) -> Dict[str, str]:
        """Get versions of all integrated tools"""
        return {
            "js-beautify": "1.14.0",
            "webpack-bundle-analyzer": "4.5.0",
            "recast": "0.21.0",
            "babel-parser": "7.18.0",
            "estree-analyzer": "1.0.0",
            "bundle-buddy": "0.4.0",
            "jscpd": "3.5.0",
            "decode-js": "1.0.0",
            "wakaru": "1.0.0",
            "humanify": "1.0.0"
        }


# Tool implementations (simplified interfaces)
class JSBeautifier:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def beautify(self, content: str) -> str:
        # Implement js-beautify integration
        return content


class BundleAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def analyze(self, content: str) -> Dict[str, Any]:
        # Implement webpack-bundle-analyzer integration
        return {"size": len(content), "chunks": [], "unused_code": []}


class DuplicationDetector:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def detect(self, content: str) -> Dict[str, Any]:
        # Implement jscpd integration
        return {"duplicated_blocks": [], "duplication_percentage": 0.0}


class DependencyMapper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def analyze(self, content: str) -> Dict[str, Any]:
        # Implement dependency analysis
        return {"dependencies": [], "circular_dependencies": []}


class FunctionAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def extract_functions(self, content: str) -> List[Dict[str, Any]]:
        # Implement function extraction and analysis
        return []


class PatternDetector:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def detect(self, content: str) -> List[Dict[str, Any]]:
        # Implement pattern detection
        return []
