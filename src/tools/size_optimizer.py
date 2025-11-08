#!/usr/bin/env python3
"""
Size Optimization Engine for Packer-InfoFinder v2.0
Advanced code size reduction and optimization tools

This module provides comprehensive size optimization using:
- recast: AST transformation for code understanding and optimization
- Tree shaking analysis for unused code detection
- Code minification and compression analysis
- Bundle splitting recommendations
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
class OptimizationSuggestion:
    """A specific optimization suggestion"""
    type: str
    description: str
    estimated_savings: int  # bytes
    priority: str  # high, medium, low
    implementation_difficulty: str  # easy, medium, hard
    code_location: Optional[str] = None
    before_example: Optional[str] = None
    after_example: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SizeOptimizationResult:
    """Complete size optimization analysis results"""
    original_size: int
    optimized_size_estimate: int
    potential_savings: int
    compression_ratio: float
    suggestions: List[OptimizationSuggestion]
    tree_shaking_opportunities: List[Dict[str, Any]]
    minification_analysis: Dict[str, Any]
    bundle_splitting_recommendations: List[Dict[str, Any]]
    analysis_time: float


class RecastAnalyzer:
    """Recast AST transformation integration for code optimization"""
    
    def __init__(self):
        self.tool_name = "recast"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if recast is available"""
        try:
            result = subprocess.run(['npm', 'list', 'recast'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def analyze_ast_optimizations(self, code: str) -> Dict[str, Any]:
        """Analyze AST for optimization opportunities using recast"""
        if not self.available:
            return self._fallback_ast_analysis(code)
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run recast analysis
            analysis_script = f'''
                const recast = require('recast');
                const fs = require('fs');
                
                try {{
                    const code = fs.readFileSync('{tmp_file_path}', 'utf8');
                    const ast = recast.parse(code);
                    
                    const analysis = {{
                        functions: [],
                        variables: [],
                        unused_code: [],
                        optimization_opportunities: []
                    }};
                    
                    // Traverse AST to find optimization opportunities
                    recast.visit(ast, {{
                        visitFunctionDeclaration(path) {{
                            const func = path.node;
                            analysis.functions.push({{
                                name: func.id ? func.id.name : 'anonymous',
                                params: func.params.length,
                                body_size: recast.print(func.body).code.length,
                                line: func.loc ? func.loc.start.line : 0
                            }});
                            this.traverse(path);
                        }},
                        
                        visitVariableDeclaration(path) {{
                            const decl = path.node;
                            decl.declarations.forEach(declarator => {{
                                if (declarator.id && declarator.id.name) {{
                                    analysis.variables.push({{
                                        name: declarator.id.name,
                                        kind: decl.kind,
                                        line: decl.loc ? decl.loc.start.line : 0
                                    }});
                                }}
                            }});
                            this.traverse(path);
                        }}
                    }});
                    
                    console.log(JSON.stringify(analysis, null, 2));
                }} catch (error) {{
                    console.error(JSON.stringify({{ error: error.message }}));
                }}
            '''
            
            cmd = ['node', '-e', analysis_script]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return self._fallback_ast_analysis(code)
                
        except Exception as e:
            return self._fallback_ast_analysis(code)
        
        finally:
            try:
                os.unlink(tmp_file_path)
            except:
                pass
    
    def _fallback_ast_analysis(self, code: str) -> Dict[str, Any]:
        """Fallback AST analysis using regex patterns"""
        functions = []
        variables = []
        
        # Extract functions
        func_pattern = r'function\s+(\w+)\s*\(([^)]*)\)\s*\{'
        for match in re.finditer(func_pattern, code, re.MULTILINE):
            func_name = match.group(1)
            params = match.group(2).split(',') if match.group(2).strip() else []
            line_num = code[:match.start()].count('\n') + 1
            
            # Estimate function body size
            body_start = match.end()
            body_size = self._estimate_function_body_size(code, body_start)
            
            functions.append({
                'name': func_name,
                'params': len(params),
                'body_size': body_size,
                'line': line_num
            })
        
        # Extract variables
        var_pattern = r'(?:var|let|const)\s+(\w+)'
        for match in re.finditer(var_pattern, code, re.MULTILINE):
            var_name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            
            variables.append({
                'name': var_name,
                'kind': 'var',  # Simplified
                'line': line_num
            })
        
        return {
            'functions': functions,
            'variables': variables,
            'unused_code': [],
            'optimization_opportunities': [],
            'fallback_analysis': True
        }
    
    def _estimate_function_body_size(self, code: str, start_pos: int) -> int:
        """Estimate function body size using brace matching"""
        brace_count = 1
        i = start_pos
        
        while i < len(code) and brace_count > 0:
            if code[i] == '{':
                brace_count += 1
            elif code[i] == '}':
                brace_count -= 1
            i += 1
        
        return i - start_pos if brace_count == 0 else 1000


class TreeShakingAnalyzer:
    """Tree shaking analysis for unused code detection"""
    
    def __init__(self):
        pass
    
    async def analyze_unused_code(self, code: str, ast_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze code for unused functions and variables"""
        opportunities = []
        
        functions = ast_analysis.get('functions', [])
        variables = ast_analysis.get('variables', [])
        
        # Find potentially unused functions
        function_names = {func['name'] for func in functions}
        function_calls = self._extract_function_calls(code)
        
        unused_functions = function_names - function_calls
        for func_name in unused_functions:
            func_info = next((f for f in functions if f['name'] == func_name), None)
            if func_info:
                opportunities.append({
                    'type': 'unused_function',
                    'name': func_name,
                    'estimated_savings': func_info['body_size'],
                    'line': func_info['line'],
                    'description': f"Function '{func_name}' appears to be unused"
                })
        
        # Find potentially unused variables
        variable_names = {var['name'] for var in variables}
        variable_usage = self._extract_variable_usage(code)
        
        unused_variables = variable_names - variable_usage
        for var_name in unused_variables:
            var_info = next((v for v in variables if v['name'] == var_name), None)
            if var_info:
                opportunities.append({
                    'type': 'unused_variable',
                    'name': var_name,
                    'estimated_savings': 50,  # Rough estimate
                    'line': var_info['line'],
                    'description': f"Variable '{var_name}' appears to be unused"
                })
        
        # Find dead code patterns
        dead_code_patterns = self._find_dead_code_patterns(code)
        opportunities.extend(dead_code_patterns)
        
        return opportunities
    
    def _extract_function_calls(self, code: str) -> set:
        """Extract function calls from code"""
        call_pattern = r'(\w+)\s*\('
        calls = set(re.findall(call_pattern, code))
        
        # Filter out keywords and common statements
        keywords = {'if', 'for', 'while', 'switch', 'catch', 'return', 'throw', 'new', 'typeof'}
        return calls - keywords
    
    def _extract_variable_usage(self, code: str) -> set:
        """Extract variable usage from code"""
        # Simple variable usage detection
        var_usage = set()
        
        # Find variable references (simplified)
        var_pattern = r'\b(\w+)\b'
        matches = re.findall(var_pattern, code)
        
        # Filter out keywords and function names
        keywords = {'var', 'let', 'const', 'function', 'if', 'else', 'for', 'while', 'return', 'true', 'false', 'null', 'undefined'}
        var_usage.update(match for match in matches if match not in keywords)
        
        return var_usage
    
    def _find_dead_code_patterns(self, code: str) -> List[Dict[str, Any]]:
        """Find common dead code patterns"""
        patterns = []
        
        # Unreachable code after return
        unreachable_pattern = r'return\s+[^;]+;[\s\n]*([^}]+)'
        for match in re.finditer(unreachable_pattern, code, re.MULTILINE | re.DOTALL):
            unreachable_code = match.group(1).strip()
            if unreachable_code and not unreachable_code.startswith('}'):
                line_num = code[:match.start()].count('\n') + 1
                patterns.append({
                    'type': 'unreachable_code',
                    'estimated_savings': len(unreachable_code),
                    'line': line_num,
                    'description': 'Code after return statement is unreachable'
                })
        
        # Empty functions
        empty_func_pattern = r'function\s+(\w+)\s*\([^)]*\)\s*\{\s*\}'
        for match in re.finditer(empty_func_pattern, code):
            func_name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            patterns.append({
                'type': 'empty_function',
                'name': func_name,
                'estimated_savings': len(match.group(0)),
                'line': line_num,
                'description': f"Empty function '{func_name}' can be removed"
            })
        
        return patterns


class MinificationAnalyzer:
    """Code minification analysis"""
    
    def __init__(self):
        pass
    
    async def analyze_minification_potential(self, code: str) -> Dict[str, Any]:
        """Analyze potential savings from minification"""
        original_size = len(code.encode('utf-8'))
        
        # Simulate minification savings
        minified_estimate = self._estimate_minified_size(code)
        
        return {
            'original_size': original_size,
            'minified_estimate': minified_estimate,
            'savings': original_size - minified_estimate,
            'compression_ratio': minified_estimate / original_size if original_size > 0 else 1,
            'techniques': self._analyze_minification_techniques(code)
        }
    
    def _estimate_minified_size(self, code: str) -> int:
        """Estimate minified code size"""
        # Remove comments
        code_no_comments = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code_no_comments = re.sub(r'/\*.*?\*/', '', code_no_comments, flags=re.DOTALL)
        
        # Remove extra whitespace
        code_compressed = re.sub(r'\s+', ' ', code_no_comments)
        code_compressed = code_compressed.strip()
        
        # Estimate further compression from variable renaming, etc.
        estimated_size = int(len(code_compressed.encode('utf-8')) * 0.7)  # 30% additional reduction
        
        return estimated_size
    
    def _analyze_minification_techniques(self, code: str) -> List[Dict[str, Any]]:
        """Analyze specific minification techniques that could be applied"""
        techniques = []
        
        # Comment removal
        comment_lines = len(re.findall(r'//.*$', code, re.MULTILINE))
        block_comments = len(re.findall(r'/\*.*?\*/', code, re.DOTALL))
        if comment_lines > 0 or block_comments > 0:
            estimated_savings = (comment_lines * 20) + (block_comments * 50)  # Rough estimate
            techniques.append({
                'technique': 'comment_removal',
                'description': 'Remove comments and documentation',
                'estimated_savings': estimated_savings,
                'impact': 'low'  # Low impact on functionality
            })
        
        # Whitespace removal
        whitespace_chars = len(re.findall(r'\s', code))
        if whitespace_chars > 1000:
            techniques.append({
                'technique': 'whitespace_removal',
                'description': 'Remove unnecessary whitespace',
                'estimated_savings': int(whitespace_chars * 0.8),
                'impact': 'low'
            })
        
        # Variable name shortening
        long_var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{8,}\b', code)
        if len(long_var_names) > 10:
            techniques.append({
                'technique': 'variable_renaming',
                'description': 'Shorten variable and function names',
                'estimated_savings': len(long_var_names) * 10,
                'impact': 'medium'  # Medium impact on readability
            })
        
        return techniques


class BundleSplittingAnalyzer:
    """Bundle splitting recommendations"""
    
    def __init__(self):
        pass
    
    async def analyze_splitting_opportunities(self, code: str, ast_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze opportunities for bundle splitting"""
        recommendations = []
        
        functions = ast_analysis.get('functions', [])
        
        # Large function splitting
        large_functions = [f for f in functions if f['body_size'] > 5000]
        if large_functions:
            recommendations.append({
                'type': 'function_splitting',
                'description': 'Split large functions into smaller modules',
                'functions': [f['name'] for f in large_functions],
                'estimated_benefit': 'Improved code splitting and lazy loading',
                'implementation': 'Extract large functions into separate modules'
            })
        
        # Vendor code separation
        vendor_patterns = ['jquery', 'lodash', 'react', 'vue', 'angular', 'bootstrap']
        vendor_code_detected = any(pattern in code.lower() for pattern in vendor_patterns)
        
        if vendor_code_detected:
            recommendations.append({
                'type': 'vendor_splitting',
                'description': 'Separate vendor libraries into dedicated bundle',
                'estimated_benefit': 'Better caching and parallel loading',
                'implementation': 'Configure webpack to create separate vendor chunk'
            })
        
        # Feature-based splitting
        feature_indicators = self._detect_feature_boundaries(code)
        if len(feature_indicators) > 1:
            recommendations.append({
                'type': 'feature_splitting',
                'description': 'Split code by feature boundaries',
                'features': list(feature_indicators.keys()),
                'estimated_benefit': 'Lazy loading of features',
                'implementation': 'Use dynamic imports for feature modules'
            })
        
        return recommendations
    
    def _detect_feature_boundaries(self, code: str) -> Dict[str, int]:
        """Detect potential feature boundaries in code"""
        features = {}
        
        # Look for common feature patterns
        feature_patterns = {
            'authentication': r'(?:login|auth|signin|signup|password)',
            'navigation': r'(?:router|route|navigate|menu)',
            'forms': r'(?:form|input|validate|submit)',
            'api': r'(?:fetch|ajax|http|api|request)',
            'ui_components': r'(?:component|widget|modal|dialog)',
            'utilities': r'(?:util|helper|common|shared)'
        }
        
        for feature_name, pattern in feature_patterns.items():
            matches = len(re.findall(pattern, code, re.IGNORECASE))
            if matches > 5:  # Threshold for significant feature presence
                features[feature_name] = matches
        
        return features


class SizeOptimizationEngine:
    """Main size optimization engine coordinating all optimization tools"""
    
    def __init__(self):
        self.recast_analyzer = RecastAnalyzer()
        self.tree_shaking_analyzer = TreeShakingAnalyzer()
        self.minification_analyzer = MinificationAnalyzer()
        self.bundle_splitting_analyzer = BundleSplittingAnalyzer()
    
    async def optimize_size(self, code: str, file_path: str) -> SizeOptimizationResult:
        """Perform comprehensive size optimization analysis"""
        import time
        start_time = time.time()
        
        original_size = len(code.encode('utf-8'))
        
        # Step 1: AST analysis using recast
        ast_analysis = await self.recast_analyzer.analyze_ast_optimizations(code)
        
        # Step 2: Tree shaking analysis
        tree_shaking_opportunities = await self.tree_shaking_analyzer.analyze_unused_code(code, ast_analysis)
        
        # Step 3: Minification analysis
        minification_analysis = await self.minification_analyzer.analyze_minification_potential(code)
        
        # Step 4: Bundle splitting recommendations
        bundle_splitting_recommendations = await self.bundle_splitting_analyzer.analyze_splitting_opportunities(code, ast_analysis)
        
        # Step 5: Generate optimization suggestions
        suggestions = self._generate_optimization_suggestions(
            ast_analysis, tree_shaking_opportunities, minification_analysis, bundle_splitting_recommendations
        )
        
        # Calculate total potential savings
        potential_savings = sum(suggestion.estimated_savings for suggestion in suggestions)
        potential_savings += minification_analysis.get('savings', 0)
        
        optimized_size_estimate = max(original_size - potential_savings, int(original_size * 0.1))  # At least 10% of original
        compression_ratio = optimized_size_estimate / original_size if original_size > 0 else 1
        
        analysis_time = time.time() - start_time
        
        return SizeOptimizationResult(
            original_size=original_size,
            optimized_size_estimate=optimized_size_estimate,
            potential_savings=potential_savings,
            compression_ratio=compression_ratio,
            suggestions=suggestions,
            tree_shaking_opportunities=tree_shaking_opportunities,
            minification_analysis=minification_analysis,
            bundle_splitting_recommendations=bundle_splitting_recommendations,
            analysis_time=analysis_time
        )
    
    def _generate_optimization_suggestions(self, ast_analysis: Dict[str, Any], 
                                         tree_shaking: List[Dict[str, Any]],
                                         minification: Dict[str, Any],
                                         bundle_splitting: List[Dict[str, Any]]) -> List[OptimizationSuggestion]:
        """Generate specific optimization suggestions"""
        suggestions = []
        
        # Tree shaking suggestions
        for opportunity in tree_shaking:
            if opportunity['type'] == 'unused_function':
                suggestions.append(OptimizationSuggestion(
                    type='remove_unused_function',
                    description=f"Remove unused function '{opportunity['name']}'",
                    estimated_savings=opportunity['estimated_savings'],
                    priority='high',
                    implementation_difficulty='easy',
                    code_location=f"Line {opportunity['line']}"
                ))
            elif opportunity['type'] == 'unused_variable':
                suggestions.append(OptimizationSuggestion(
                    type='remove_unused_variable',
                    description=f"Remove unused variable '{opportunity['name']}'",
                    estimated_savings=opportunity['estimated_savings'],
                    priority='medium',
                    implementation_difficulty='easy',
                    code_location=f"Line {opportunity['line']}"
                ))
        
        # Large function suggestions
        functions = ast_analysis.get('functions', [])
        large_functions = [f for f in functions if f['body_size'] > 2000]
        
        for func in large_functions:
            suggestions.append(OptimizationSuggestion(
                type='refactor_large_function',
                description=f"Refactor large function '{func['name']}' into smaller functions",
                estimated_savings=int(func['body_size'] * 0.1),  # 10% reduction estimate
                priority='medium',
                implementation_difficulty='medium',
                code_location=f"Line {func['line']}"
            ))
        
        # Minification suggestions
        for technique in minification.get('techniques', []):
            suggestions.append(OptimizationSuggestion(
                type=f"minification_{technique['technique']}",
                description=technique['description'],
                estimated_savings=technique['estimated_savings'],
                priority='high' if technique['impact'] == 'low' else 'medium',
                implementation_difficulty='easy'
            ))
        
        # Bundle splitting suggestions
        for recommendation in bundle_splitting:
            suggestions.append(OptimizationSuggestion(
                type=f"bundle_splitting_{recommendation['type']}",
                description=recommendation['description'],
                estimated_savings=1000,  # Rough estimate for bundle splitting benefits
                priority='medium',
                implementation_difficulty='medium'
            ))
        
        return suggestions


# Example usage and testing
async def main():
    """Example usage of the size optimization engine"""
    
    # Sample JavaScript code with optimization opportunities
    sample_code = '''
    // This is a comment that could be removed
    function largeUnusedFunction() {
        // This function is never called
        let unusedVariable = "this is not used";
        
        for (let i = 0; i < 1000; i++) {
            console.log("This is a large function that could be optimized");
            if (i % 100 === 0) {
                console.log("Progress:", i);
            }
        }
        
        return "unused result";
    }
    
    function anotherLargeFunction() {
        // Another large function that could be split
        let data = [];
        
        // Data processing
        for (let i = 0; i < 500; i++) {
            data.push({
                id: i,
                value: Math.random(),
                processed: false
            });
        }
        
        // Data transformation
        data = data.map(item => ({
            ...item,
            processed: true,
            timestamp: Date.now()
        }));
        
        // Data filtering
        data = data.filter(item => item.value > 0.5);
        
        return data;
    }
    
    function actuallyUsedFunction() {
        console.log("This function is actually used");
        return anotherLargeFunction();
    }
    
    // Main execution
    const result = actuallyUsedFunction();
    console.log("Result:", result.length);
    
    /* This is a block comment
       that spans multiple lines
       and could be removed for production */
    
    const veryLongVariableNameThatCouldBeShortened = "some value";
    console.log(veryLongVariableNameThatCouldBeShortened);
    ''' * 100  # Repeat to make it larger
    
    # Initialize size optimization engine
    optimizer = SizeOptimizationEngine()
    
    # Perform optimization analysis
    print("🔍 Running comprehensive size optimization analysis...")
    result = await optimizer.optimize_size(sample_code, "large_file.js")
    
    # Display results
    print(f"\n📊 Size Optimization Results:")
    print(f"   • Original size: {result.original_size:,} bytes ({result.original_size / (1024*1024):.1f} MB)")
    print(f"   • Optimized estimate: {result.optimized_size_estimate:,} bytes ({result.optimized_size_estimate / (1024*1024):.1f} MB)")
    print(f"   • Potential savings: {result.potential_savings:,} bytes ({(result.potential_savings / result.original_size) * 100:.1f}%)")
    print(f"   • Compression ratio: {result.compression_ratio:.2f}")
    print(f"   • Analysis time: {result.analysis_time:.2f}s")
    
    print(f"\n🎯 Top Optimization Suggestions:")
    sorted_suggestions = sorted(result.suggestions, key=lambda x: x.estimated_savings, reverse=True)
    for i, suggestion in enumerate(sorted_suggestions[:5], 1):
        print(f"   {i}. {suggestion.description}")
        print(f"      Savings: {suggestion.estimated_savings:,} bytes")
        print(f"      Priority: {suggestion.priority}, Difficulty: {suggestion.implementation_difficulty}")
        if suggestion.code_location:
            print(f"      Location: {suggestion.code_location}")
        print()
    
    print(f"\n🌳 Tree Shaking Opportunities: {len(result.tree_shaking_opportunities)}")
    for opp in result.tree_shaking_opportunities[:3]:
        print(f"   • {opp['description']} (saves {opp['estimated_savings']} bytes)")
    
    print(f"\n📦 Bundle Splitting Recommendations: {len(result.bundle_splitting_recommendations)}")
    for rec in result.bundle_splitting_recommendations:
        print(f"   • {rec['description']}")
        print(f"     Benefit: {rec['estimated_benefit']}")


if __name__ == "__main__":
    asyncio.run(main())
