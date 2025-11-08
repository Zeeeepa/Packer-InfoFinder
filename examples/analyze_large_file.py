#!/usr/bin/env python3
"""
Example: Analyze Large JavaScript File using Packer-InfoFinder v2.0
Demonstrates how to analyze a 22MB GitHub CLI index.js file

This example shows how to use the complete analysis pipeline:
- 20-agent parallel processing for massive files
- Function-by-function analysis and explanation
- Bundle composition understanding
- Code size optimization suggestions
- Dependency mapping and relationship analysis
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.parallel_analysis_engine import ParallelAnalysisEngine
from tools.function_analyzer import FunctionAnalysisEngine
from tools.bundle_analyzer import BundleAnalysisEngine
from tools.size_optimizer import SizeOptimizationEngine


async def analyze_large_javascript_file(file_path: str):
    """
    Complete analysis pipeline for large JavaScript files
    
    Args:
        file_path: Path to the JavaScript file to analyze (e.g., "C:\\Users\\L\\Desktop\\index.js")
    """
    
    print(f"🚀 Starting comprehensive analysis of: {file_path}")
    print(f"📊 Using 20-agent parallel processing for maximum performance")
    
    # Read the file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        file_size_mb = len(code.encode('utf-8')) / (1024 * 1024)
        print(f"📁 File size: {file_size_mb:.1f} MB ({len(code.encode('utf-8')):,} bytes)")
        
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        return
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    # Initialize all analysis engines
    print(f"\n🔧 Initializing analysis engines...")
    parallel_engine = ParallelAnalysisEngine(num_workers=20)
    function_engine = FunctionAnalysisEngine()
    bundle_engine = BundleAnalysisEngine()
    size_optimizer = SizeOptimizationEngine()
    
    total_start_time = time.time()
    
    # Step 1: Parallel processing analysis (fastest, runs first)
    print(f"\n⚡ Step 1: Running 20-agent parallel analysis...")
    parallel_result = await parallel_engine.analyze_massive_file(code, file_path)
    
    print(f"   ✅ Parallel analysis completed in {parallel_result.total_processing_time:.2f}s")
    print(f"   📊 Found {parallel_result.total_functions:,} functions")
    print(f"   🔧 Used {parallel_result.workers_used} workers")
    print(f"   📈 Processing speed: {parallel_result.performance_stats['bytes_per_second'] / (1024*1024):.1f} MB/s")
    
    # Step 2: Function analysis (detailed function understanding)
    print(f"\n🔍 Step 2: Running detailed function analysis...")
    function_result = await function_engine.analyze_functions(code)
    
    print(f"   ✅ Function analysis completed in {function_result.analysis_time:.2f}s")
    print(f"   📊 Analyzed {function_result.total_functions} functions")
    
    # Step 3: Bundle analysis (composition and dependencies)
    print(f"\n📦 Step 3: Running bundle composition analysis...")
    bundle_result = await bundle_engine.analyze_bundle(code, file_path)
    
    print(f"   ✅ Bundle analysis completed in {bundle_result.analysis_time:.2f}s")
    print(f"   📊 Found {len(bundle_result.modules)} modules")
    print(f"   🔗 Identified {len(bundle_result.dependencies)} dependencies")
    
    # Step 4: Size optimization analysis
    print(f"\n🎯 Step 4: Running size optimization analysis...")
    optimization_result = await size_optimizer.optimize_size(code, file_path)
    
    print(f"   ✅ Optimization analysis completed in {optimization_result.analysis_time:.2f}s")
    print(f"   💾 Potential savings: {optimization_result.potential_savings:,} bytes ({(optimization_result.potential_savings / optimization_result.original_size) * 100:.1f}%)")
    
    total_time = time.time() - total_start_time
    
    # Display comprehensive results
    print(f"\n" + "="*80)
    print(f"📊 COMPREHENSIVE ANALYSIS RESULTS")
    print(f"="*80)
    
    print(f"\n⏱️  Performance Summary:")
    print(f"   • Total analysis time: {total_time:.2f}s")
    print(f"   • File size: {file_size_mb:.1f} MB")
    print(f"   • Processing speed: {file_size_mb / total_time:.1f} MB/s")
    print(f"   • Parallel efficiency: {parallel_result.performance_stats['parallelization_efficiency']:.1%}")
    
    print(f"\n🔍 Function Analysis Summary:")
    print(f"   • Total functions: {function_result.total_functions:,}")
    print(f"   • Complexity distribution:")
    for complexity_level, count in function_result.complexity_distribution.items():
        if count > 0:
            print(f"     - {complexity_level}: {count:,}")
    
    print(f"\n📦 Bundle Composition Summary:")
    print(f"   • Total size: {bundle_result.total_size:,} bytes")
    if bundle_result.gzipped_size:
        print(f"   • Gzipped estimate: {bundle_result.gzipped_size:,} bytes")
    print(f"   • Modules: {len(bundle_result.modules)}")
    print(f"   • Size breakdown:")
    for category, size in bundle_result.size_breakdown.items():
        if size > 0:
            percentage = (size / bundle_result.total_size) * 100
            print(f"     - {category.replace('_', ' ').title()}: {size:,} bytes ({percentage:.1f}%)")
    
    print(f"\n🎯 Optimization Opportunities:")
    print(f"   • Potential size reduction: {optimization_result.potential_savings:,} bytes ({(optimization_result.potential_savings / optimization_result.original_size) * 100:.1f}%)")
    print(f"   • Optimized size estimate: {optimization_result.optimized_size_estimate:,} bytes")
    print(f"   • Compression ratio: {optimization_result.compression_ratio:.2f}")
    
    print(f"\n🔧 Top Optimization Suggestions:")
    sorted_suggestions = sorted(optimization_result.suggestions, key=lambda x: x.estimated_savings, reverse=True)
    for i, suggestion in enumerate(sorted_suggestions[:5], 1):
        print(f"   {i}. {suggestion.description}")
        print(f"      💾 Savings: {suggestion.estimated_savings:,} bytes")
        print(f"      🎯 Priority: {suggestion.priority}")
        if suggestion.code_location:
            print(f"      📍 Location: {suggestion.code_location}")
        print()
    
    print(f"\n🔗 Top Dependencies:")
    sorted_deps = sorted(bundle_result.dependencies.items(), key=lambda x: x[1], reverse=True)
    for dep, size in sorted_deps[:5]:
        print(f"   • {dep}: {size:,} bytes")
    
    if bundle_result.duplicates:
        print(f"\n🔄 Code Duplication Found:")
        print(f"   • {len(bundle_result.duplicates)} instances of duplicate code")
        total_duplicate_savings = sum(dup['estimated_savings'] for dup in bundle_result.duplicates)
        print(f"   • Potential savings from deduplication: {total_duplicate_savings:,} bytes")
    
    print(f"\n📈 Performance Metrics:")
    print(f"   • Functions per second: {function_result.total_functions / total_time:.0f}")
    print(f"   • Bytes per second: {len(code.encode('utf-8')) / total_time:,.0f}")
    print(f"   • Workers utilized: {parallel_result.workers_used}/20")
    
    print(f"\n✅ Analysis complete! Your {file_size_mb:.1f}MB file has been comprehensively analyzed.")
    print(f"🚀 Ready for optimization and size reduction!")


async def main():
    """Main function to run the analysis"""
    
    # Default file path (can be changed)
    default_file_path = r"C:\Users\L\Desktop\index.js"
    
    # Check if file path provided as argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = default_file_path
        print(f"💡 Using default file path: {file_path}")
        print(f"💡 To analyze a different file, run: python analyze_large_file.py <path_to_file>")
    
    # Run the analysis
    await analyze_large_javascript_file(file_path)


if __name__ == "__main__":
    # Example usage:
    # python examples/analyze_large_file.py "C:\Users\L\Desktop\index.js"
    # python examples/analyze_large_file.py "/path/to/your/large/bundle.js"
    
    print("🔍 Packer-InfoFinder v2.0 - Large File Analysis")
    print("=" * 60)
    
    asyncio.run(main())
            'cache_directory': './cache',
            'max_memory_size': 256 * 1024 * 1024,  # 256MB
            'chunking_strategy': 'function_based',
            'cache_strategy': 'lru'
        }
    }
    
    # Initialize analyzer
    analyzer = AdvancedJSAnalyzer(config)
    
    # Example file path (replace with your actual file)
    file_path = "C:\\Users\\L\\Desktop\\index.js"
    
    print("🚀 Packer-InfoFinder v2.0 - Large File Analysis Example")
    print("=" * 60)
    print(f"📄 Target file: {file_path}")
    
    # Check if file exists
    if not Path(file_path).exists():
        print("❌ File not found. Please update the file_path variable.")
        print("💡 This example is designed for your 22MB GitHub CLI index.js")
        return
    
    try:
        # Read file and check size
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_size = len(content)
        print(f"📊 File size: {file_size:,} bytes ({file_size / (1024*1024):.1f} MB)")
        
        if file_size > 10 * 1024 * 1024:  # > 10MB
            print("⚡ Large file detected - using incremental analysis")
            result = await analyzer.analyze_large_file(file_path, content)
        else:
            print("🔍 Standard file analysis")
            result = await analyzer.analyze_file(file_path, content)
        
        # Display results
        print("\n📊 Analysis Results:")
        print(f"   • Analysis time: {result.analysis_time:.2f} seconds")
        print(f"   • Functions found: {len(result.functions)}")
        print(f"   • Total variables: {result.total_variables}")
        print(f"   • Total imports: {result.total_imports}")
        print(f"   • Total exports: {result.total_exports}")
        print(f"   • Cyclomatic complexity: {result.cyclomatic_complexity}")
        print(f"   • Quality score: {result.quality_score:.2f}")
        print(f"   • Performance score: {result.performance_score:.2f}")
        print(f"   • Maintainability score: {result.maintainability_score:.2f}")
        
        # Show optimization suggestions
        if result.optimizations:
            print(f"\n🎯 Optimization Opportunities ({len(result.optimizations)}):")
            for opt in result.optimizations[:3]:  # Show top 3
                savings = f" (saves {opt.estimated_savings:,} bytes)" if opt.estimated_savings > 0 else ""
                print(f"   • {opt.title}{savings}")
                print(f"     Priority: {opt.priority}, Effort: {opt.implementation_effort}")
        
        # Show findings
        if result.findings:
            print(f"\n🔍 Analysis Findings ({len(result.findings)}):")
            for finding in result.findings[:5]:  # Show top 5
                print(f"   • [{finding.severity.value.upper()}] {finding.title}")
                if finding.recommendation:
                    print(f"     → {finding.recommendation}")
        
        # Cache statistics
        cache_stats = analyzer.cache_manager.get_stats()
        print(f"\n📈 Cache Performance:")
        print(f"   • Hit rate: {cache_stats['hit_rate']:.1%}")
        print(f"   • Memory entries: {cache_stats['memory_entries']}")
        print(f"   • Memory utilization: {cache_stats['memory_utilization']:.1%}")
        print(f"   • Chunks processed: {cache_stats['chunks_processed']}")
        print(f"   • Chunks cached: {cache_stats['chunks_cached']}")
        
        print("\n✅ Analysis complete!")
        print("💡 For a full HTML report, use: python Packer-InfoFinder-v2.py -f <file> --advanced --large-file")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


async def demonstrate_chunking_strategies():
    """Demonstrate different chunking strategies for large files"""
    
    print("\n🔧 Chunking Strategy Demonstration")
    print("=" * 40)
    
    # Sample large content (simulated)
    sample_content = """
    function largeFunction1() {
        // Complex function with many lines
        for (let i = 0; i < 1000; i++) {
            console.log(i);
        }
    }
    
    const arrowFunction = () => {
        return "arrow function";
    };
    
    class LargeClass {
        constructor() {
            this.data = new Array(1000).fill(0);
        }
        
        method1() {
            return this.data.length;
        }
    }
    """ * 100  # Repeat to make it larger
    
    from src.caching.incremental_cache import IncrementalCacheManager, ChunkingStrategy
    
    strategies = [
        ChunkingStrategy.FIXED_SIZE,
        ChunkingStrategy.FUNCTION_BASED,
        ChunkingStrategy.ADAPTIVE
    ]
    
    for strategy in strategies:
        cache_config = {
            'chunk_size': 1024,  # Small chunks for demo
            'chunking_strategy': strategy.value
        }
        
        cache_manager = IncrementalCacheManager(cache_config)
        chunks = cache_manager._create_chunks(sample_content)
        
        print(f"\n📦 {strategy.value.replace('_', ' ').title()} Strategy:")
        print(f"   • Total chunks: {len(chunks)}")
        print(f"   • Average chunk size: {sum(len(c.content) for c in chunks) // len(chunks):,} bytes")
        print(f"   • Size range: {min(len(c.content) for c in chunks):,} - {max(len(c.content) for c in chunks):,} bytes")


if __name__ == "__main__":
    print("🚀 Running Large File Analysis Examples...")
    
    # Run the main example
    asyncio.run(analyze_large_file_example())
    
    # Demonstrate chunking strategies
    asyncio.run(demonstrate_chunking_strategies())
    
    print("\n🎯 Next Steps:")
    print("1. Update the file_path variable with your actual file location")
    print("2. Run: python Packer-InfoFinder-v2.py -f <your-file> --advanced --large-file")
    print("3. Open the generated HTML report for detailed analysis")
