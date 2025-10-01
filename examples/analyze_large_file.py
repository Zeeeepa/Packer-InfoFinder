#!/usr/bin/env python3
"""
Example: Analyzing Large JavaScript Files with Packer-InfoFinder v2.0

This example demonstrates how to analyze massive JavaScript files
like the 22MB GitHub CLI index.js using advanced analysis capabilities.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.append('..')
from src.core.advanced_js_analyzer import AdvancedJSAnalyzer, AnalysisType


async def analyze_large_file_example():
    """Example of analyzing a large JavaScript file"""
    
    # Configuration for large file analysis
    config = {
        'enabled_analyses': [
            AnalysisType.STRUCTURE,
            AnalysisType.FUNCTIONS,
            AnalysisType.DEPENDENCIES,
            AnalysisType.BUNDLE,
            AnalysisType.OPTIMIZATION
        ],
        'chunk_size': 1024 * 1024,  # 1MB chunks
        'enable_caching': True,
        'parallel_analysis': True,
        'cache_config': {
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
