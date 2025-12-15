#!/usr/bin/env python3
"""
Monitor formatting latency from logs.

This script watches the log file and extracts formatting-related latency metrics.
"""

import re
import time
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class FormattingLogEntry:
    """Represents a formatting log entry."""
    timestamp: str
    request_id: str
    operation: str
    latency_ms: float
    model: Optional[str] = None
    details: str = ""


def parse_log_line(line: str) -> Optional[FormattingLogEntry]:
    """Parse a log line and extract formatting-related information."""
    # Pattern: timestamp | level | [request_id] | file:line | function | message
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \| (\w+)\s+\| \[([^\]]+)\] \| ([^|]+) \| ([^|]+) \| (.+)'
    
    match = re.match(pattern, line)
    if not match:
        return None
    
    timestamp, level, request_id, location, function, message = match.groups()
    
    # Look for formatting-related log entries
    formatting_patterns = [
        (r'⏱ LLM call \(([^)]+)\) completed in ([\d.]+)s', 'llm_call'),
        (r'Formatting results', 'format_start'),
        (r'Successfully generated natural language summary', 'format_success'),
        (r'Retrieved (?:structured )?prompt from prompts\.yaml', 'prompt_retrieved'),
    ]
    
    for pattern, op_type in formatting_patterns:
        match_op = re.search(pattern, message)
        if match_op:
            if op_type == 'llm_call':
                model = match_op.group(1)
                latency_s = float(match_op.group(2))
                return FormattingLogEntry(
                    timestamp=timestamp,
                    request_id=request_id,
                    operation=op_type,
                    latency_ms=latency_s * 1000,
                    model=model,
                    details=message
                )
            else:
                return FormattingLogEntry(
                    timestamp=timestamp,
                    request_id=request_id,
                    operation=op_type,
                    latency_ms=0,
                    details=message
                )
    
    return None


def analyze_logs(log_file: Path, last_n_lines: Optional[int] = None) -> List[FormattingLogEntry]:
    """Analyze log file and extract formatting entries."""
    entries = []
    
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return entries
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
        
        if last_n_lines:
            lines = lines[-last_n_lines:]
        
        for line in lines:
            entry = parse_log_line(line.strip())
            if entry:
                entries.append(entry)
    
    return entries


def print_summary(entries: List[FormattingLogEntry]):
    """Print summary of formatting entries."""
    if not entries:
        print("No formatting entries found in logs.")
        return
    
    llm_calls = [e for e in entries if e.operation == 'llm_call']
    format_starts = [e for e in entries if e.operation == 'format_start']
    format_successes = [e for e in entries if e.operation == 'format_success']
    
    print("\n" + "="*70)
    print("Formatting Latency Analysis from Logs")
    print("="*70)
    
    if llm_calls:
        latencies = [e.latency_ms for e in llm_calls]
        models = [e.model for e in llm_calls if e.model]
        
        print(f"\nLLM Formatting Calls: {len(llm_calls)}")
        if latencies:
            print(f"  Average Latency: {sum(latencies) / len(latencies):.2f}ms")
            print(f"  Min Latency: {min(latencies):.2f}ms")
            print(f"  Max Latency: {max(latencies):.2f}ms")
        
        if models:
            model_counts = {}
            for m in models:
                model_counts[m] = model_counts.get(m, 0) + 1
            print(f"  Models Used: {dict(model_counts)}")
        
        print(f"\nRecent Formatting Calls:")
        for entry in llm_calls[-5:]:  # Show last 5
            print(f"  [{entry.request_id[:8]}] {entry.model}: {entry.latency_ms:.2f}ms at {entry.timestamp}")
    
    if format_starts:
        print(f"\nFormat Operations Started: {len(format_starts)}")
    
    if format_successes:
        print(f"Format Operations Completed: {len(format_successes)}")
    
    # Compare with baseline
    if llm_calls:
        avg_latency = sum(e.latency_ms for e in llm_calls) / len(llm_calls)
        baseline = 2320  # 2.32s from old logs
        improvement = ((baseline - avg_latency) / baseline) * 100
        
        print(f"\nPerformance Comparison:")
        print(f"  Baseline (gpt-4.1-mini): ~2320ms")
        print(f"  Current Average: {avg_latency:.2f}ms")
        print(f"  Improvement: {improvement:.1f}% faster")
        
        if avg_latency < 1500:
            print(f"  ✓ Target achieved (<1500ms)")
        else:
            print(f"  ⚠ Still above target")


def watch_logs(log_file: Path, interval: float = 1.0):
    """Watch log file for new formatting entries."""
    print(f"Watching log file: {log_file}")
    print("Press Ctrl+C to stop\n")
    
    last_size = log_file.stat().st_size if log_file.exists() else 0
    
    try:
        while True:
            if log_file.exists():
                current_size = log_file.stat().st_size
                
                if current_size > last_size:
                    # Read new lines
                    with open(log_file, 'r') as f:
                        f.seek(last_size)
                        new_lines = f.readlines()
                        
                        for line in new_lines:
                            entry = parse_log_line(line.strip())
                            if entry and entry.operation == 'llm_call':
                                print(f"[{entry.timestamp}] {entry.model}: {entry.latency_ms:.2f}ms")
                    
                    last_size = current_size
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\nStopped watching logs.")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor formatting latency from logs")
    parser.add_argument(
        "--log-file",
        default="logs/travel_booking.log",
        help="Path to log file (default: logs/travel_booking.log)"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch log file for new entries"
    )
    parser.add_argument(
        "--last",
        type=int,
        help="Analyze last N lines of log file"
    )
    
    args = parser.parse_args()
    
    log_file = Path(args.log_file)
    
    if args.watch:
        watch_logs(log_file)
    else:
        entries = analyze_logs(log_file, last_n_lines=args.last)
        print_summary(entries)


if __name__ == "__main__":
    main()


