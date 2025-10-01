#!/usr/bin/env python3
"""
Code Analysis Engine for Packer-InfoFinder v2.0
Integrates multiple JavaScript code analysis and function understanding tools

This module provides unified code analysis capabilities using:
- decode-js: Advanced AST analysis for function understanding
- wakaru: Modern webpack decompiler for bundle analysis
- humanify: AI-powered code understanding and variable naming
- babel-parser: Modern JavaScript parsing for function extraction
- recast: AST transformation for code understanding
- jscpd: Code duplication detection for size optimization
"""

import asyncio
import json
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import re


class SecuritySeverity(Enum):
    """Security finding severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityFinding:
    """Represents a security finding from analysis"""
    tool: str
    severity: SecuritySeverity
    title: str
    description: str
    line: Optional[int] = None
    column: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None
    cwe_id: Optional[str] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['severity'] = self.severity.value
        return result


@dataclass
class SecurityAnalysisResult:
    """Complete security analysis results"""
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings: List[SecurityFinding]
    tools_used: List[str]
    analysis_time: float
    file_hash: str
    vulnerable_libraries: List[Dict[str, Any]]
    security_score: float  # 0.0 (very insecure) to 1.0 (secure)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'total_findings': self.total_findings,
            'findings_by_severity': self.findings_by_severity,
            'findings': [f.to_dict() for f in self.findings],
            'tools_used': self.tools_used,
            'analysis_time': self.analysis_time,
            'file_hash': self.file_hash,
            'vulnerable_libraries': self.vulnerable_libraries,
            'security_score': self.security_score
        }


class JSXRayAnalyzer:
    """js-x-ray AST security analysis integration"""
    
    def __init__(self):
        self.tool_name = "js-x-ray"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if js-x-ray is available"""
        try:
            result = subprocess.run(['npm', 'list', 'js-x-ray'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def analyze(self, code: str, file_path: str) -> List[SecurityFinding]:
        """Analyze JavaScript code using js-x-ray"""
        if not self.available:
            return []
        
        findings = []
        
        try:
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run js-x-ray analysis
            cmd = ['node', '-e', f'''
                const {{ runASTAnalysis }} = require('js-x-ray');
                const fs = require('fs');
                
                try {{
                    const code = fs.readFileSync('{tmp_file_path}', 'utf8');
                    const result = runASTAnalysis(code);
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
                analysis_result = json.loads(stdout.decode())
                findings.extend(self._parse_jsxray_results(analysis_result, file_path))
            
        except Exception as e:
            # Add error as finding
            findings.append(SecurityFinding(
                tool=self.tool_name,
                severity=SecuritySeverity.INFO,
                title="Analysis Error",
                description=f"js-x-ray analysis failed: {str(e)}",
                recommendation="Check if js-x-ray is properly installed"
            ))
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        return findings
    
    def _parse_jsxray_results(self, result: Dict[str, Any], file_path: str) -> List[SecurityFinding]:
        """Parse js-x-ray analysis results into SecurityFindings"""
        findings = []
        
        # Parse warnings
        for warning in result.get('warnings', []):
            severity = self._map_jsxray_severity(warning.get('kind', 'info'))
            
            finding = SecurityFinding(
                tool=self.tool_name,
                severity=severity,
                title=f"Suspicious Pattern: {warning.get('kind', 'Unknown')}",
                description=warning.get('value', 'No description available'),
                line=warning.get('location', {}).get('start', {}).get('line'),
                column=warning.get('location', {}).get('start', {}).get('column'),
                recommendation=self._get_jsxray_recommendation(warning.get('kind', ''))
            )
            findings.append(finding)
        
        # Parse dependencies for suspicious patterns
        for dep_name, dep_info in result.get('dependencies', {}).items():
            if dep_info.get('flags', []):
                for flag in dep_info['flags']:
                    finding = SecurityFinding(
                        tool=self.tool_name,
                        severity=SecuritySeverity.MEDIUM,
                        title=f"Suspicious Dependency: {dep_name}",
                        description=f"Dependency flagged for: {flag}",
                        recommendation=f"Review dependency '{dep_name}' for security issues"
                    )
                    findings.append(finding)
        
        return findings
    
    def _map_jsxray_severity(self, kind: str) -> SecuritySeverity:
        """Map js-x-ray warning kinds to severity levels"""
        severity_map = {
            'obfuscated-code': SecuritySeverity.HIGH,
            'encoded-literal': SecuritySeverity.MEDIUM,
            'suspicious-literal': SecuritySeverity.MEDIUM,
            'suspicious-file': SecuritySeverity.HIGH,
            'weak-crypto': SecuritySeverity.HIGH,
            'unsafe-import': SecuritySeverity.MEDIUM,
            'unsafe-regex': SecuritySeverity.MEDIUM,
            'short-identifiers': SecuritySeverity.LOW,
            'minified-code': SecuritySeverity.INFO
        }
        return severity_map.get(kind, SecuritySeverity.INFO)
    
    def _get_jsxray_recommendation(self, kind: str) -> str:
        """Get recommendation based on js-x-ray warning kind"""
        recommendations = {
            'obfuscated-code': "Review obfuscated code for malicious intent. Consider deobfuscation tools.",
            'encoded-literal': "Examine encoded strings for suspicious content or data exfiltration.",
            'suspicious-literal': "Investigate suspicious string literals for potential security issues.",
            'suspicious-file': "File contains multiple suspicious patterns. Conduct thorough review.",
            'weak-crypto': "Replace weak cryptographic functions with secure alternatives.",
            'unsafe-import': "Review dynamic imports for potential code injection vulnerabilities.",
            'unsafe-regex': "Check regex patterns for ReDoS (Regular Expression Denial of Service) vulnerabilities.",
            'short-identifiers': "Code may be minified or obfuscated. Consider using source maps.",
            'minified-code': "Code appears to be minified. Use source maps for better analysis."
        }
        return recommendations.get(kind, "Review code for potential security issues.")


class ESLintSecurityAnalyzer:
    """ESLint Security plugin integration"""
    
    def __init__(self):
        self.tool_name = "eslint-security"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if ESLint and security plugin are available"""
        try:
            result = subprocess.run(['npx', 'eslint', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def analyze(self, code: str, file_path: str) -> List[SecurityFinding]:
        """Analyze JavaScript code using ESLint security rules"""
        if not self.available:
            return []
        
        findings = []
        
        try:
            # Create temporary file and ESLint config
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Create ESLint config with security rules
            eslint_config = {
                "plugins": ["security"],
                "extends": ["plugin:security/recommended"],
                "parserOptions": {
                    "ecmaVersion": 2022,
                    "sourceType": "module"
                },
                "env": {
                    "browser": True,
                    "node": True,
                    "es6": True
                }
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
                json.dump(eslint_config, config_file)
                config_file_path = config_file.name
            
            # Run ESLint with security rules
            cmd = ['npx', 'eslint', '--config', config_file_path, '--format', 'json', tmp_file_path]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            # ESLint returns non-zero exit code when issues are found
            if stdout:
                eslint_results = json.loads(stdout.decode())
                findings.extend(self._parse_eslint_results(eslint_results, file_path))
            
        except Exception as e:
            findings.append(SecurityFinding(
                tool=self.tool_name,
                severity=SecuritySeverity.INFO,
                title="Analysis Error",
                description=f"ESLint security analysis failed: {str(e)}",
                recommendation="Check if ESLint and eslint-plugin-security are properly installed"
            ))
        
        finally:
            # Clean up temporary files
            try:
                os.unlink(tmp_file_path)
                os.unlink(config_file_path)
            except:
                pass
        
        return findings
    
    def _parse_eslint_results(self, results: List[Dict[str, Any]], file_path: str) -> List[SecurityFinding]:
        """Parse ESLint results into SecurityFindings"""
        findings = []
        
        for file_result in results:
            for message in file_result.get('messages', []):
                severity = self._map_eslint_severity(message.get('severity', 1))
                
                finding = SecurityFinding(
                    tool=self.tool_name,
                    severity=severity,
                    title=f"Security Rule: {message.get('ruleId', 'Unknown')}",
                    description=message.get('message', 'No description available'),
                    line=message.get('line'),
                    column=message.get('column'),
                    recommendation=self._get_eslint_recommendation(message.get('ruleId', ''))
                )
                findings.append(finding)
        
        return findings
    
    def _map_eslint_severity(self, severity: int) -> SecuritySeverity:
        """Map ESLint severity to SecuritySeverity"""
        if severity == 2:  # Error
            return SecuritySeverity.HIGH
        elif severity == 1:  # Warning
            return SecuritySeverity.MEDIUM
        else:
            return SecuritySeverity.LOW
    
    def _get_eslint_recommendation(self, rule_id: str) -> str:
        """Get recommendation based on ESLint security rule"""
        recommendations = {
            'security/detect-unsafe-regex': "Review regex patterns for ReDoS vulnerabilities",
            'security/detect-buffer-noassert': "Use assert methods when working with buffers",
            'security/detect-child-process': "Validate input when using child processes",
            'security/detect-disable-mustache-escape': "Avoid disabling mustache escaping",
            'security/detect-eval-with-expression': "Avoid using eval() with dynamic expressions",
            'security/detect-no-csrf-before-method-override': "Implement CSRF protection",
            'security/detect-non-literal-fs-filename': "Validate file paths to prevent directory traversal",
            'security/detect-non-literal-regexp': "Use literal regex patterns when possible",
            'security/detect-non-literal-require': "Avoid dynamic require() calls",
            'security/detect-object-injection': "Validate object properties to prevent injection",
            'security/detect-possible-timing-attacks': "Use constant-time comparison for sensitive data",
            'security/detect-pseudoRandomBytes': "Use cryptographically secure random number generation"
        }
        return recommendations.get(rule_id, "Review code for potential security issues")


class RetireJSAnalyzer:
    """RetireJS vulnerable library detection integration"""
    
    def __init__(self):
        self.tool_name = "retirejs"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if RetireJS is available"""
        try:
            result = subprocess.run(['retire', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def analyze(self, code: str, file_path: str) -> Tuple[List[SecurityFinding], List[Dict[str, Any]]]:
        """Analyze JavaScript code for vulnerable libraries using RetireJS"""
        if not self.available:
            return [], []
        
        findings = []
        vulnerable_libs = []
        
        try:
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name
            
            # Run RetireJS analysis
            cmd = ['retire', '--outputformat', 'json', '--outputpath', '/dev/stdout', tmp_file_path]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if stdout:
                try:
                    retire_results = json.loads(stdout.decode())
                    findings, vulnerable_libs = self._parse_retire_results(retire_results, file_path)
                except json.JSONDecodeError:
                    # RetireJS might output non-JSON format in some cases
                    pass
            
        except Exception as e:
            findings.append(SecurityFinding(
                tool=self.tool_name,
                severity=SecuritySeverity.INFO,
                title="Analysis Error",
                description=f"RetireJS analysis failed: {str(e)}",
                recommendation="Check if RetireJS is properly installed"
            ))
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        return findings, vulnerable_libs
    
    def _parse_retire_results(self, results: List[Dict[str, Any]], file_path: str) -> Tuple[List[SecurityFinding], List[Dict[str, Any]]]:
        """Parse RetireJS results into SecurityFindings and vulnerable library list"""
        findings = []
        vulnerable_libs = []
        
        for result in results:
            for vulnerability in result.get('results', []):
                for vuln in vulnerability.get('vulnerabilities', []):
                    severity = self._map_retire_severity(vuln.get('severity', 'medium'))
                    
                    finding = SecurityFinding(
                        tool=self.tool_name,
                        severity=severity,
                        title=f"Vulnerable Library: {vulnerability.get('component', 'Unknown')}",
                        description=f"Version {vulnerability.get('version', 'unknown')} has known vulnerabilities",
                        recommendation=f"Update to version {vuln.get('below', 'latest')} or higher",
                        cwe_id=vuln.get('cwe', [None])[0] if vuln.get('cwe') else None
                    )
                    findings.append(finding)
                    
                    # Add to vulnerable libraries list
                    vulnerable_libs.append({
                        'component': vulnerability.get('component', 'Unknown'),
                        'version': vulnerability.get('version', 'unknown'),
                        'vulnerabilities': vulnerability.get('vulnerabilities', []),
                        'severity': severity.value
                    })
        
        return findings, vulnerable_libs
    
    def _map_retire_severity(self, severity: str) -> SecuritySeverity:
        """Map RetireJS severity to SecuritySeverity"""
        severity_map = {
            'critical': SecuritySeverity.CRITICAL,
            'high': SecuritySeverity.HIGH,
            'medium': SecuritySeverity.MEDIUM,
            'low': SecuritySeverity.LOW
        }
        return severity_map.get(severity.lower(), SecuritySeverity.MEDIUM)


class CustomPatternAnalyzer:
    """Custom security pattern detection for malware and suspicious code"""
    
    def __init__(self):
        self.tool_name = "custom-patterns"
        self.patterns = self._load_security_patterns()
    
    def _load_security_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load custom security patterns for detection"""
        return {
            'malware_indicators': [
                {
                    'pattern': r'eval\s*\(\s*["\'].*["\']\s*\)',
                    'severity': 'high',
                    'title': 'Dynamic Code Execution',
                    'description': 'Use of eval() with string literals can indicate code injection'
                },
                {
                    'pattern': r'document\.write\s*\(\s*.*\s*\)',
                    'severity': 'medium',
                    'title': 'DOM Manipulation',
                    'description': 'document.write() can be used for XSS attacks'
                },
                {
                    'pattern': r'innerHTML\s*=\s*.*',
                    'severity': 'medium',
                    'title': 'Unsafe HTML Injection',
                    'description': 'innerHTML assignment without sanitization can lead to XSS'
                }
            ],
            'obfuscation_indicators': [
                {
                    'pattern': r'\\x[0-9a-fA-F]{2}',
                    'severity': 'medium',
                    'title': 'Hex Encoded Strings',
                    'description': 'Hex-encoded strings may indicate obfuscation'
                },
                {
                    'pattern': r'\\u[0-9a-fA-F]{4}',
                    'severity': 'medium',
                    'title': 'Unicode Encoded Strings',
                    'description': 'Unicode-encoded strings may indicate obfuscation'
                },
                {
                    'pattern': r'String\.fromCharCode\s*\(',
                    'severity': 'medium',
                    'title': 'Character Code Obfuscation',
                    'description': 'String.fromCharCode() used for string obfuscation'
                }
            ],
            'crypto_indicators': [
                {
                    'pattern': r'crypto\.createHash\s*\(\s*["\']md5["\']',
                    'severity': 'high',
                    'title': 'Weak Hash Algorithm',
                    'description': 'MD5 is cryptographically broken and should not be used'
                },
                {
                    'pattern': r'crypto\.createHash\s*\(\s*["\']sha1["\']',
                    'severity': 'medium',
                    'title': 'Weak Hash Algorithm',
                    'description': 'SHA1 is deprecated and should be replaced with SHA256 or higher'
                }
            ]
        }
    
    async def analyze(self, code: str, file_path: str) -> List[SecurityFinding]:
        """Analyze code using custom security patterns"""
        findings = []
        
        for category, patterns in self.patterns.items():
            for pattern_info in patterns:
                matches = re.finditer(pattern_info['pattern'], code, re.IGNORECASE | re.MULTILINE)
                
                for match in matches:
                    # Calculate line number
                    line_num = code[:match.start()].count('\n') + 1
                    
                    # Extract code snippet
                    lines = code.split('\n')
                    snippet_start = max(0, line_num - 2)
                    snippet_end = min(len(lines), line_num + 1)
                    code_snippet = '\n'.join(lines[snippet_start:snippet_end])
                    
                    severity = SecuritySeverity(pattern_info['severity'])
                    
                    finding = SecurityFinding(
                        tool=self.tool_name,
                        severity=severity,
                        title=pattern_info['title'],
                        description=pattern_info['description'],
                        line=line_num,
                        column=match.start() - code.rfind('\n', 0, match.start()),
                        code_snippet=code_snippet,
                        recommendation=f"Review {category.replace('_', ' ')} pattern at line {line_num}"
                    )
                    findings.append(finding)
        
        return findings


class SecurityAnalysisEngine:
    """Main security analysis engine coordinating all security tools"""
    
    def __init__(self):
        self.analyzers = {
            'js-x-ray': JSXRayAnalyzer(),
            'eslint-security': ESLintSecurityAnalyzer(),
            'retirejs': RetireJSAnalyzer(),
            'custom-patterns': CustomPatternAnalyzer()
        }
    
    async def analyze(self, code: str, file_path: str) -> SecurityAnalysisResult:
        """Perform comprehensive security analysis"""
        import time
        start_time = time.time()
        
        all_findings = []
        vulnerable_libraries = []
        tools_used = []
        
        # Calculate file hash
        file_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Run all available analyzers
        for tool_name, analyzer in self.analyzers.items():
            try:
                if tool_name == 'retirejs':
                    findings, vuln_libs = await analyzer.analyze(code, file_path)
                    vulnerable_libraries.extend(vuln_libs)
                else:
                    findings = await analyzer.analyze(code, file_path)
                
                if findings:
                    all_findings.extend(findings)
                    tools_used.append(tool_name)
                    
            except Exception as e:
                # Add error as finding but continue with other tools
                error_finding = SecurityFinding(
                    tool=tool_name,
                    severity=SecuritySeverity.INFO,
                    title=f"{tool_name} Analysis Error",
                    description=f"Tool failed with error: {str(e)}",
                    recommendation=f"Check {tool_name} installation and configuration"
                )
                all_findings.append(error_finding)
        
        # Calculate analysis metrics
        analysis_time = time.time() - start_time
        total_findings = len(all_findings)
        
        # Count findings by severity
        findings_by_severity = {
            'critical': len([f for f in all_findings if f.severity == SecuritySeverity.CRITICAL]),
            'high': len([f for f in all_findings if f.severity == SecuritySeverity.HIGH]),
            'medium': len([f for f in all_findings if f.severity == SecuritySeverity.MEDIUM]),
            'low': len([f for f in all_findings if f.severity == SecuritySeverity.LOW]),
            'info': len([f for f in all_findings if f.severity == SecuritySeverity.INFO])
        }
        
        # Calculate security score (0.0 = very insecure, 1.0 = secure)
        security_score = self._calculate_security_score(findings_by_severity, total_findings)
        
        return SecurityAnalysisResult(
            total_findings=total_findings,
            findings_by_severity=findings_by_severity,
            findings=all_findings,
            tools_used=tools_used,
            analysis_time=analysis_time,
            file_hash=file_hash,
            vulnerable_libraries=vulnerable_libraries,
            security_score=security_score
        )
    
    def _calculate_security_score(self, findings_by_severity: Dict[str, int], total_findings: int) -> float:
        """Calculate overall security score based on findings"""
        if total_findings == 0:
            return 1.0  # Perfect score if no issues found
        
        # Weight different severity levels
        severity_weights = {
            'critical': 10,
            'high': 5,
            'medium': 2,
            'low': 1,
            'info': 0.1
        }
        
        # Calculate weighted score
        weighted_issues = sum(
            findings_by_severity[severity] * weight 
            for severity, weight in severity_weights.items()
        )
        
        # Normalize to 0-1 scale (lower is worse)
        # Use logarithmic scale to prevent single critical issue from dominating
        import math
        max_possible_score = total_findings * severity_weights['critical']
        normalized_score = 1.0 - (math.log(weighted_issues + 1) / math.log(max_possible_score + 1))
        
        return max(0.0, min(1.0, normalized_score))


# Example usage and testing
async def main():
    """Example usage of the security analysis engine"""
    
    # Sample JavaScript code with security issues
    sample_code = '''
    // Sample code with various security issues
    function processUserInput(input) {
        // Dangerous eval usage
        eval("var result = " + input);
        
        // XSS vulnerability
        document.getElementById("output").innerHTML = input;
        
        // Weak crypto
        const crypto = require('crypto');
        const hash = crypto.createHash('md5').update(input).digest('hex');
        
        return hash;
    }
    
    // Obfuscated string
    var secret = String.fromCharCode(72, 101, 108, 108, 111);
    
    // Unicode obfuscation
    var encoded = "\\u0048\\u0065\\u006c\\u006c\\u006f";
    '''
    
    # Initialize security engine
    security_engine = SecurityAnalysisEngine()
    
    # Perform analysis
    print("🔍 Running comprehensive security analysis...")
    result = await security_engine.analyze(sample_code, "sample.js")
    
    # Display results
    print(f"\n📊 Security Analysis Results:")
    print(f"   • Total findings: {result.total_findings}")
    print(f"   • Security score: {result.security_score:.2f}")
    print(f"   • Analysis time: {result.analysis_time:.2f}s")
    print(f"   • Tools used: {', '.join(result.tools_used)}")
    
    print(f"\n🚨 Findings by severity:")
    for severity, count in result.findings_by_severity.items():
        if count > 0:
            print(f"   • {severity.upper()}: {count}")
    
    print(f"\n🔍 Detailed findings:")
    for i, finding in enumerate(result.findings[:5], 1):  # Show first 5
        print(f"   {i}. [{finding.severity.value.upper()}] {finding.title}")
        print(f"      Tool: {finding.tool}")
        print(f"      Description: {finding.description}")
        if finding.line:
            print(f"      Location: Line {finding.line}")
        if finding.recommendation:
            print(f"      Recommendation: {finding.recommendation}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
