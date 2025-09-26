#!/usr/bin/env python3
"""
Performance benchmark script to compare caching vs non-caching performance
"""
import subprocess
import json
import time
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

def run_verification(enable_cache=True, session_suffix=""):
    """Run verification with or without caching"""
    cache_flag = "" if enable_cache else "--no-cache"
    session_id = f"benchmark-{'cached' if enable_cache else 'uncached'}-{session_suffix}"

    cmd = [
        "python", "main.py", "verify",
        "--session-id", session_id,
        "--verbose"
    ]
    if not enable_cache:
        cmd.append("--no-cache")

    print(f"{Fore.CYAN}Running verification with caching {'ENABLED' if enable_cache else 'DISABLED'}...{Style.RESET_ALL}")

    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        end_time = time.time()

        if result.returncode == 0:
            # Load result file to get performance metrics
            results_path = f"./results/{session_id}.json"
            if Path(results_path).exists():
                with open(results_path, 'r') as f:
                    data = json.load(f)
                return {
                    "success": True,
                    "total_time": end_time - start_time,
                    "claims_processed": data.get("performance", {}).get("claims_processed", 0),
                    "avg_time_per_claim": data.get("performance", {}).get("avg_time_per_claim", 0),
                    "session_id": session_id,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            else:
                return {
                    "success": False,
                    "error": "Result file not found",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
        else:
            return {
                "success": False,
                "error": f"Process failed with code {result.returncode}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Process timed out after 30 minutes"
        }

def main():
    print(f"{Fore.GREEN}{'='*60}")
    print(f"Strands Document Verifier Performance Benchmark")
    print(f"{'='*60}{Style.RESET_ALL}")

    timestamp = int(time.time())

    # Run with caching enabled
    print(f"\n{Fore.YELLOW}Phase 1: Running with CACHING ENABLED{Style.RESET_ALL}")
    cached_result = run_verification(enable_cache=True, session_suffix=str(timestamp))

    if not cached_result["success"]:
        print(f"{Fore.RED}Cached run failed: {cached_result['error']}{Style.RESET_ALL}")
        print(f"STDOUT: {cached_result.get('stdout', '')}")
        print(f"STDERR: {cached_result.get('stderr', '')}")
        return

    # Wait a bit to ensure cache expiry (if needed)
    print(f"\n{Fore.YELLOW}Waiting 10 seconds before uncached run...{Style.RESET_ALL}")
    time.sleep(10)

    # Run with caching disabled
    print(f"\n{Fore.YELLOW}Phase 2: Running with CACHING DISABLED{Style.RESET_ALL}")
    uncached_result = run_verification(enable_cache=False, session_suffix=str(timestamp))

    if not uncached_result["success"]:
        print(f"{Fore.RED}Uncached run failed: {uncached_result['error']}{Style.RESET_ALL}")
        print(f"STDOUT: {uncached_result.get('stdout', '')}")
        print(f"STDERR: {uncached_result.get('stderr', '')}")
        return

    # Compare results
    print(f"\n{Fore.GREEN}{'='*60}")
    print(f"PERFORMANCE COMPARISON RESULTS")
    print(f"{'='*60}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}WITH CACHING:{Style.RESET_ALL}")
    print(f"  Total Time: {cached_result['total_time']:.2f} seconds")
    print(f"  Claims Processed: {cached_result['claims_processed']}")
    print(f"  Avg Time/Claim: {cached_result['avg_time_per_claim']:.2f} seconds")
    print(f"  Session ID: {cached_result['session_id']}")

    print(f"\n{Fore.CYAN}WITHOUT CACHING:{Style.RESET_ALL}")
    print(f"  Total Time: {uncached_result['total_time']:.2f} seconds")
    print(f"  Claims Processed: {uncached_result['claims_processed']}")
    print(f"  Avg Time/Claim: {uncached_result['avg_time_per_claim']:.2f} seconds")
    print(f"  Session ID: {uncached_result['session_id']}")

    # Calculate improvements
    if uncached_result['total_time'] > 0:
        time_improvement = ((uncached_result['total_time'] - cached_result['total_time']) / uncached_result['total_time']) * 100
        speed_multiplier = uncached_result['total_time'] / cached_result['total_time']

        print(f"\n{Fore.GREEN}PERFORMANCE IMPROVEMENTS:{Style.RESET_ALL}")
        print(f"  Time Reduction: {time_improvement:.1f}%")
        print(f"  Speed Multiplier: {speed_multiplier:.2f}x faster")

        if time_improvement > 0:
            print(f"  {Fore.GREEN}✓ Caching provided significant performance benefits!{Style.RESET_ALL}")
        else:
            print(f"  {Fore.YELLOW}⚠ Caching didn't provide expected benefits{Style.RESET_ALL}")

    print(f"\n{Fore.BLUE}Result files saved for detailed analysis:{Style.RESET_ALL}")
    print(f"  Cached: ./results/{cached_result['session_id']}.json")
    print(f"  Uncached: ./results/{uncached_result['session_id']}.json")

    # Ask user if they want to view table results
    print(f"\n{Fore.YELLOW}View detailed results in table format?{Style.RESET_ALL}")
    response = input("Enter 'c' for cached, 'u' for uncached, 'b' for both, or any other key to skip: ").lower()

    if response in ['c', 'b']:
        print(f"\n{Fore.CYAN}=== CACHED RESULTS TABLE ==={Style.RESET_ALL}")
        subprocess.run([
            "python", "main.py", "view-table", cached_result['session_id']
        ])

    if response in ['u', 'b']:
        print(f"\n{Fore.CYAN}=== UNCACHED RESULTS TABLE ==={Style.RESET_ALL}")
        subprocess.run([
            "python", "main.py", "view-table", uncached_result['session_id']
        ])

if __name__ == "__main__":
    main()