#!/usr/bin/env python3
"""
Function Analysis Engine for Packer-InfoFinder v2.0
Advanced function-by-function analysis and understanding tools

This module provides comprehensive function analysis using:
- decode-js: Advanced AST analysis for function understanding
- babel-parser: Modern JavaScript parsing for function extraction
- recast: AST transformation for code understanding
- humanify: AI-powered code understanding and variable naming
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
class FunctionInfo:
    """Detailed information about a JavaScript function"""
    name: str
    type: str  # function_declaration, arrow_function, method, etc.
    line_start: int
    line_end: int
    parameters: List[str]
    body: str
    size_bytes: int
    complexity: int
    calls_made: List[str]  # Functions this function calls
    variables_used: List[str]
    return_type: Optional[str] = None
    description: Optional[str] = None
    optimization_suggestions: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class FunctionAnalysisResult:
    """Complete function analysis results"""
    total_functions: int
    functions: List[FunctionInfo]
    function_call_graph: Dict[str, List[str]]
    complexity_distribution: Dict[str, int]
    size_distribution: Dict[str, int]
    optimization_opportunities: List[Dict[str, Any]]
    analysis_time: float


class DecodeJSAnalyzer:
    """decode-js integration for advanced AST analysis"""
    
    def __init__(self):
        self.tool_name = "decode-js"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if decode-js is available"""
        try:
            result = subprocess.run(['npm', 'list', 'decode-js'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def analyze_functions(self, code: str) -> List[FunctionInfo]:
        """Analyze functions using decode-js"""
        if not self.available:
            return self._fallback_function_analysis(code)
        
        functions = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run decode-js analysis
            cmd = ['node', '-e', f'''
                const {{ decode }} = require('decode-js');
                const fs = require('fs');
                
                try {{
                    const code = fs.readFileSync('{tmp_file_path}', 'utf8');
                    const result = decode(code);
                    console.log(JSON.stringify(result, null, 2));
                }} catch (error) {{
                    console.error(JSON.stringify({{ error: error.message }}));
                }}
            ''']
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                decode_result = json.loads(stdout.decode())
                functions = self._parse_decode_results(decode_result, code)
            
        except Exception as e:
            # Fall back to regex-based analysis
            functions = self._fallback_function_analysis(code)
        
        finally:
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        return functions
    
    def _parse_decode_results(self, result: Dict[str, Any], code: str) -> List[FunctionInfo]:
        """Parse decode-js results into FunctionInfo objects"""
        functions = []
        
        # Parse AST nodes for functions
        if 'ast' in result:
            functions.extend(self._extract_functions_from_ast(result['ast'], code))
        
        return functions
    
    def _extract_functions_from_ast(self, ast: Dict[str, Any], code: str) -> List[FunctionInfo]:
        """Extract functions from AST"""
        functions = []
        
        def traverse_ast(node, parent_name=""):
            if isinstance(node, dict):
                node_type = node.get('type', '')
                
                if node_type in ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']:
                    func_info = self._create_function_info_from_ast(node, code, parent_name)
                    if func_info:
                        functions.append(func_info)
                
                # Recursively traverse child nodes
                for key, value in node.items():
                    if key != 'type':
                        traverse_ast(value, parent_name)
            
            elif isinstance(node, list):
                for item in node:
                    traverse_ast(item, parent_name)
        
        traverse_ast(ast)
        return functions
    
    def _create_function_info_from_ast(self, node: Dict[str, Any], code: str, parent_name: str) -> Optional[FunctionInfo]:
        """Create FunctionInfo from AST node"""
        try:
            # Extract function name
            name = "anonymous"
            if node.get('id') and node['id'].get('name'):
                name = node['id']['name']
            elif parent_name:
                name = f"{parent_name}_anonymous"
            
            # Extract parameters
            parameters = []
            if 'params' in node:
                for param in node['params']:
                    if isinstance(param, dict) and param.get('name'):
                        parameters.append(param['name'])
            
            # Extract location info
            loc = node.get('loc', {})
            line_start = loc.get('start', {}).get('line', 0)
            line_end = loc.get('end', {}).get('line', 0)
            
            # Extract function body
            body = self._extract_function_body_from_ast(node, code)
            
            return FunctionInfo(
                name=name,
                type=node.get('type', 'unknown'),
                line_start=line_start,
                line_end=line_end,
                parameters=parameters,
                body=body,
                size_bytes=len(body.encode('utf-8')),
                complexity=self._calculate_complexity(body),
                calls_made=self._extract_function_calls(body),
                variables_used=self._extract_variables(body)
            )
        
        except Exception:
            return None
    
    def _extract_function_body_from_ast(self, node: Dict[str, Any], code: str) -> str:
        """Extract function body from AST node"""
        if 'body' in node:
            # Try to extract from location info
            loc = node.get('loc', {})
            if loc.get('start') and loc.get('end'):
                lines = code.split('\n')
                start_line = loc['start']['line'] - 1
                end_line = loc['end']['line'] - 1
                
                if 0 <= start_line < len(lines) and 0 <= end_line < len(lines):
                    return '\n'.join(lines[start_line:end_line + 1])
        
        return ""
    
    def _fallback_function_analysis(self, code: str) -> List[FunctionInfo]:
        """Fallback regex-based function analysis when decode-js is not available"""
        functions = []
        lines = code.split('\n')
        
        # Function patterns
        patterns = {
            'function_declaration': r'function\s+(\w+)\s*\(([^)]*)\)\s*\{',
            'arrow_function': r'(?:const|let|var)\s+(\w+)\s*=\s*(?:\(([^)]*)\)|(\w+))\s*=>\s*[{(]',
            'method_definition': r'(\w+)\s*\(([^)]*)\)\s*\{',
            'class_method': r'(?:static\s+)?(\w+)\s*\(([^)]*)\)\s*\{'
        }
        
        for pattern_name, pattern in patterns.items():
            for match in re.finditer(pattern, code, re.MULTILINE):
                func_name = match.group(1) if match.groups() else 'anonymous'
                params_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else ''
                
                # Parse parameters
                parameters = []
                if params_str:
                    parameters = [p.strip() for p in params_str.split(',') if p.strip()]
                
                # Find function body
                start_pos = match.start()
                line_start = code[:start_pos].count('\n') + 1
                body, line_end = self._extract_function_body_regex(code, start_pos)
                
                functions.append(FunctionInfo(
                    name=func_name,
                    type=pattern_name,
                    line_start=line_start,
                    line_end=line_end,
                    parameters=parameters,
                    body=body,
                    size_bytes=len(body.encode('utf-8')),
                    complexity=self._calculate_complexity(body),
                    calls_made=self._extract_function_calls(body),
                    variables_used=self._extract_variables(body)
                ))
        
        return functions
    
    def _extract_function_body_regex(self, code: str, start_pos: int) -> Tuple[str, int]:
        """Extract function body using brace matching"""
        # Find opening brace
        i = start_pos
        while i < len(code) and code[i] != '{':
            i += 1
        
        if i >= len(code):
            return "", code[:start_pos].count('\n') + 1
        
        # Match braces
        brace_count = 1
        start_body = i
        i += 1
        
        while i < len(code) and brace_count > 0:
            if code[i] == '{':
                brace_count += 1
            elif code[i] == '}':
                brace_count -= 1
            i += 1
        
        body = code[start_body:i] if brace_count == 0 else code[start_body:start_body + 1000]
        line_end = code[:i].count('\n') + 1
        
        return body, line_end
    
    def _calculate_complexity(self, function_body: str) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1  # Base complexity
        
        # Count decision points
        decision_keywords = ['if', 'else', 'for', 'while', 'switch', 'case', 'catch', '&&', '||', '?']
        
        for keyword in decision_keywords:
            complexity += function_body.count(keyword)
        
        return complexity
    
    def _extract_function_calls(self, function_body: str) -> List[str]:
        """Extract function calls from function body"""
        calls = []
        
        # Pattern for function calls
        call_pattern = r'(\w+)\s*\('
        matches = re.findall(call_pattern, function_body)
        
        # Filter out keywords and common statements
        keywords = {'if', 'for', 'while', 'switch', 'catch', 'return', 'throw', 'new', 'typeof'}
        calls = [call for call in matches if call not in keywords]
        
        return list(set(calls))  # Remove duplicates
    
    def _extract_variables(self, function_body: str) -> List[str]:
        """Extract variable declarations from function body"""
        variables = []
        
        # Pattern for variable declarations
        var_patterns = [
            r'(?:var|let|const)\s+(\w+)',
            r'function\s+(\w+)',
            r'class\s+(\w+)'
        ]
        
        for pattern in var_patterns:
            matches = re.findall(pattern, function_body)
            variables.extend(matches)
        
        return list(set(variables))  # Remove duplicates


class BabelParserAnalyzer:
    """Babel parser integration for modern JavaScript parsing"""
    
    def __init__(self):
        self.tool_name = "babel-parser"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if babel-parser is available"""
        try:
            result = subprocess.run(['npm', 'list', '@babel/parser'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def parse_and_analyze(self, code: str) -> Dict[str, Any]:
        """Parse JavaScript using Babel parser"""
        if not self.available:
            return {}
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run Babel parser
            cmd = ['node', '-e', f'''
                const parser = require('@babel/parser');
                const fs = require('fs');
                
                try {{
                    const code = fs.readFileSync('{tmp_file_path}', 'utf8');
                    const ast = parser.parse(code, {{
                        sourceType: 'module',
                        allowImportExportEverywhere: true,
                        allowReturnOutsideFunction: true,
                        plugins: [
                            'jsx',
                            'typescript',
                            'decorators-legacy',
                            'classProperties',
                            'asyncGenerators',
                            'functionBind',
                            'exportDefaultFrom',
                            'exportNamespaceFrom',
                            'dynamicImport',
                            'nullishCoalescingOperator',
                            'optionalChaining'
                        ]
                    }});
                    
                    // Simplify AST for JSON serialization
                    const simplifiedAst = JSON.stringify(ast, (key, value) => {{
                        if (key === 'start' || key === 'end' || key === 'loc') {{
                            return value;
                        }}
                        if (typeof value === 'object' && value !== null && Object.keys(value).length > 20) {{
                            return {{ type: value.type, simplified: true }};
                        }}
                        return value;
                    }});
                    
                    console.log(simplifiedAst);
                }} catch (error) {{
                    console.error(JSON.stringify({{ error: error.message }}));
                }}
            ''']
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return json.loads(stdout.decode())
            
        except Exception as e:
            pass
        
        finally:
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        return {}


class HumanifyAnalyzer:
    """Humanify integration for AI-powered code understanding"""
    
    def __init__(self):
        self.tool_name = "humanify"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if humanify is available"""
        try:
            result = subprocess.run(['npm', 'list', 'humanify'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def humanify_functions(self, functions: List[FunctionInfo]) -> List[FunctionInfo]:
        """Use humanify to improve function understanding"""
        if not self.available:
            return self._fallback_humanify(functions)
        
        enhanced_functions = []
        
        for func in functions:
            try:
                # Create temporary file with function code
                with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                    tmp_file.write(func.body)
                    tmp_file_path = tmp_file.name
                
                # Run humanify
                cmd = ['npx', 'humanify', tmp_file_path]
                
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    humanified_code = stdout.decode()
                    
                    # Update function with humanified version
                    enhanced_func = FunctionInfo(
                        name=func.name,
                        type=func.type,
                        line_start=func.line_start,
                        line_end=func.line_end,
                        parameters=func.parameters,
                        body=humanified_code,
                        size_bytes=len(humanified_code.encode('utf-8')),
                        complexity=func.complexity,
                        calls_made=func.calls_made,
                        variables_used=func.variables_used,
                        description=self._generate_function_description(func),
                        optimization_suggestions=self._generate_optimization_suggestions(func)
                    )
                    enhanced_functions.append(enhanced_func)
                else:
                    enhanced_functions.append(func)
                
            except Exception:
                enhanced_functions.append(func)
            
            finally:
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
        
        return enhanced_functions
    
    def _fallback_humanify(self, functions: List[FunctionInfo]) -> List[FunctionInfo]:
        """Fallback function enhancement when humanify is not available"""
        enhanced_functions = []
        
        for func in functions:
            enhanced_func = FunctionInfo(
                name=func.name,
                type=func.type,
                line_start=func.line_start,
                line_end=func.line_end,
                parameters=func.parameters,
                body=func.body,
                size_bytes=func.size_bytes,
                complexity=func.complexity,
                calls_made=func.calls_made,
                variables_used=func.variables_used,
                description=self._generate_function_description(func),
                optimization_suggestions=self._generate_optimization_suggestions(func)
            )
            enhanced_functions.append(enhanced_func)
        
        return enhanced_functions
    
    def _generate_function_description(self, func: FunctionInfo) -> str:
        """Generate human-readable function description"""
        descriptions = []
        
        # Basic description
        if func.parameters:
            descriptions.append(f"Function '{func.name}' takes {len(func.parameters)} parameters: {', '.join(func.parameters)}")
        else:
            descriptions.append(f"Function '{func.name}' takes no parameters")
        
        # Complexity description
        if func.complexity > 10:
            descriptions.append("This is a complex function with high cyclomatic complexity")
        elif func.complexity > 5:
            descriptions.append("This function has moderate complexity")
        else:
            descriptions.append("This is a simple function")
        
        # Size description
        if func.size_bytes > 5000:
            descriptions.append("This is a large function that might benefit from refactoring")
        elif func.size_bytes > 1000:
            descriptions.append("This is a medium-sized function")
        else:
            descriptions.append("This is a small function")
        
        return ". ".join(descriptions) + "."
    
    def _generate_optimization_suggestions(self, func: FunctionInfo) -> List[str]:
        """Generate optimization suggestions for function"""
        suggestions = []
        
        # Size-based suggestions
        if func.size_bytes > 5000:
            suggestions.append("Consider breaking this large function into smaller, more focused functions")
        
        # Complexity-based suggestions
        if func.complexity > 10:
            suggestions.append("High complexity detected - consider simplifying conditional logic")
        
        # Parameter-based suggestions
        if len(func.parameters) > 5:
            suggestions.append("Consider using an options object instead of many parameters")
        
        # Code pattern suggestions
        if 'console.log' in func.body:
            suggestions.append("Remove console.log statements for production code")
        
        if func.body.count('for') > 3:
            suggestions.append("Multiple loops detected - consider using array methods like map/filter/reduce")
        
        return suggestions


class FunctionAnalysisEngine:
    """Main function analysis engine coordinating all function analysis tools"""
    
    def __init__(self):
        self.decode_analyzer = DecodeJSAnalyzer()
        self.babel_analyzer = BabelParserAnalyzer()
        self.humanify_analyzer = HumanifyAnalyzer()
    
    async def analyze_functions(self, code: str) -> FunctionAnalysisResult:
        """Perform comprehensive function analysis"""
        import time
        start_time = time.time()
        
        # Step 1: Extract functions using decode-js
        functions = await self.decode_analyzer.analyze_functions(code)
        
        # Step 2: Enhance with Babel parser analysis
        babel_ast = await self.babel_analyzer.parse_and_analyze(code)
        
        # Step 3: Enhance with humanify
        enhanced_functions = await self.humanify_analyzer.humanify_functions(functions)
        
        # Step 4: Build function call graph
        call_graph = self._build_call_graph(enhanced_functions)
        
        # Step 5: Calculate distributions and optimizations
        complexity_dist = self._calculate_complexity_distribution(enhanced_functions)
        size_dist = self._calculate_size_distribution(enhanced_functions)
        optimizations = self._identify_optimization_opportunities(enhanced_functions)
        
        analysis_time = time.time() - start_time
        
        return FunctionAnalysisResult(
            total_functions=len(enhanced_functions),
            functions=enhanced_functions,
            function_call_graph=call_graph,
            complexity_distribution=complexity_dist,
            size_distribution=size_dist,
            optimization_opportunities=optimizations,
            analysis_time=analysis_time
        )
    
    def _build_call_graph(self, functions: List[FunctionInfo]) -> Dict[str, List[str]]:
        """Build function call graph"""
        call_graph = {}
        function_names = {func.name for func in functions}
        
        for func in functions:
            # Only include calls to functions that exist in our analysis
            calls = [call for call in func.calls_made if call in function_names]
            call_graph[func.name] = calls
        
        return call_graph
    
    def _calculate_complexity_distribution(self, functions: List[FunctionInfo]) -> Dict[str, int]:
        """Calculate complexity distribution"""
        distribution = {
            'simple (1-5)': 0,
            'moderate (6-10)': 0,
            'complex (11-20)': 0,
            'very_complex (21+)': 0
        }
        
        for func in functions:
            if func.complexity <= 5:
                distribution['simple (1-5)'] += 1
            elif func.complexity <= 10:
                distribution['moderate (6-10)'] += 1
            elif func.complexity <= 20:
                distribution['complex (11-20)'] += 1
            else:
                distribution['very_complex (21+)'] += 1
        
        return distribution
    
    def _calculate_size_distribution(self, functions: List[FunctionInfo]) -> Dict[str, int]:
        """Calculate size distribution"""
        distribution = {
            'small (<500 bytes)': 0,
            'medium (500-2000 bytes)': 0,
            'large (2000-5000 bytes)': 0,
            'very_large (5000+ bytes)': 0
        }
        
        for func in functions:
            if func.size_bytes < 500:
                distribution['small (<500 bytes)'] += 1
            elif func.size_bytes < 2000:
                distribution['medium (500-2000 bytes)'] += 1
            elif func.size_bytes < 5000:
                distribution['large (2000-5000 bytes)'] += 1
            else:
                distribution['very_large (5000+ bytes)'] += 1
        
        return distribution
    
    def _identify_optimization_opportunities(self, functions: List[FunctionInfo]) -> List[Dict[str, Any]]:
        """Identify optimization opportunities across all functions"""
        opportunities = []
        
        # Large function optimization
        large_functions = [f for f in functions if f.size_bytes > 5000]
        if large_functions:
            opportunities.append({
                'type': 'large_functions',
                'count': len(large_functions),
                'estimated_savings': sum(f.size_bytes for f in large_functions) * 0.3,
                'priority': 'high',
                'description': f"Found {len(large_functions)} large functions that could be refactored"
            })
        
        # Complex function optimization
        complex_functions = [f for f in functions if f.complexity > 10]
        if complex_functions:
            opportunities.append({
                'type': 'complex_functions',
                'count': len(complex_functions),
                'estimated_savings': len(complex_functions) * 100,
                'priority': 'medium',
                'description': f"Found {len(complex_functions)} complex functions that could be simplified"
            })
        
        # Duplicate function detection (simplified)
        function_signatures = {}
        for func in functions:
            signature = f"{len(func.parameters)}_{func.size_bytes}"
            if signature in function_signatures:
                function_signatures[signature].append(func.name)
            else:
                function_signatures[signature] = [func.name]
        
        duplicates = {sig: names for sig, names in function_signatures.items() if len(names) > 1}
        if duplicates:
            opportunities.append({
                'type': 'potential_duplicates',
                'count': sum(len(names) - 1 for names in duplicates.values()),
                'estimated_savings': sum(len(names) - 1 for names in duplicates.values()) * 500,
                'priority': 'medium',
                'description': f"Found {len(duplicates)} groups of potentially duplicate functions"
            })
        
        return opportunities


# Example usage and testing
async def main():
    """Example usage of the function analysis engine"""
    
    # Sample JavaScript code with various function types
    sample_code = '''
    // Function declaration
    function calculateTotal(items) {
        let total = 0;
        for (let i = 0; i < items.length; i++) {
            if (items[i].price > 0) {
                total += items[i].price;
                console.log('Adding item:', items[i].name);
            }
        }
        return total;
    }
    
    // Arrow function
    const processData = (data) => {
        return data.map(item => ({
            ...item,
            processed: true,
            timestamp: Date.now()
        }));
    };
    
    // Class with methods
    class DataProcessor {
        constructor(options = {}) {
            this.options = options;
            this.cache = new Map();
        }
        
        process(input) {
            if (this.cache.has(input)) {
                return this.cache.get(input);
            }
            
            const result = this.complexProcessing(input);
            this.cache.set(input, result);
            return result;
        }
        
        complexProcessing(input) {
            // Complex processing logic
            let result = input;
            
            for (let i = 0; i < 10; i++) {
                if (i % 2 === 0) {
                    result = result.map(x => x * 2);
                } else {
                    result = result.filter(x => x > 0);
                }
                
                if (result.length === 0) {
                    break;
                }
            }
            
            return result;
        }
        
        static createDefault() {
            return new DataProcessor({ 
                cacheSize: 100,
                timeout: 5000 
            });
        }
    }
    
    // Async function
    async function fetchAndProcess(url) {
        try {
            const response = await fetch(url);
            const data = await response.json();
            
            const processor = DataProcessor.createDefault();
            const processed = processor.process(data);
            
            return {
                success: true,
                data: processed,
                total: calculateTotal(processed)
            };
        } catch (error) {
            console.error('Error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }
    '''
    
    # Initialize function analysis engine
    function_engine = FunctionAnalysisEngine()
    
    # Perform analysis
    print("🔍 Running comprehensive function analysis...")
    result = await function_engine.analyze_functions(sample_code)
    
    # Display results
    print(f"\n📊 Function Analysis Results:")
    print(f"   • Total functions: {result.total_functions}")
    print(f"   • Analysis time: {result.analysis_time:.2f}s")
    
    print(f"\n📈 Complexity Distribution:")
    for complexity_level, count in result.complexity_distribution.items():
        if count > 0:
            print(f"   • {complexity_level}: {count}")
    
    print(f"\n📏 Size Distribution:")
    for size_level, count in result.size_distribution.items():
        if count > 0:
            print(f"   • {size_level}: {count}")
    
    print(f"\n🔍 Function Details:")
    for i, func in enumerate(result.functions[:5], 1):  # Show first 5
        print(f"   {i}. {func.name} ({func.type})")
        print(f"      Lines: {func.line_start}-{func.line_end}")
        print(f"      Parameters: {', '.join(func.parameters) if func.parameters else 'None'}")
        print(f"      Size: {func.size_bytes} bytes")
        print(f"      Complexity: {func.complexity}")
        if func.description:
            print(f"      Description: {func.description}")
        print()
    
    print(f"\n🎯 Optimization Opportunities:")
    for opt in result.optimization_opportunities:
        print(f"   • {opt['type']}: {opt['description']}")
        print(f"     Priority: {opt['priority']}, Estimated savings: {opt['estimated_savings']} bytes")


if __name__ == "__main__":
    asyncio.run(main())

