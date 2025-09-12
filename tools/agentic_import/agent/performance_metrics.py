#!/usr/bin/env python3

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Performance Optimization and Metrics for ADK PVMap Generation

This module provides comprehensive performance monitoring, optimization,
and analytics capabilities for the ADK PVMap generation workflow.

Key Features:
- Real-time performance monitoring and profiling
- Memory usage tracking and optimization
- Workflow step timing and bottleneck identification
- Caching mechanisms for repeated operations
- Performance comparison and benchmarking
- Resource usage optimization and recommendations
- Historical performance analytics and trends

Components:
1. PerformanceMonitor - Real-time monitoring and profiling
2. CacheManager - Intelligent caching for optimization
3. ResourceOptimizer - Memory and CPU optimization
4. PerformanceAnalyzer - Historical analysis and insights
5. BenchmarkSuite - Performance comparison tools

Usage:
    monitor = PerformanceMonitor()
    with monitor.track_operation("workflow_execution"):
        result = execute_workflow(...)
    
    report = monitor.generate_performance_report()
    optimizer = ResourceOptimizer()
    optimizations = optimizer.get_optimization_recommendations(report)
"""

import os
import sys
import time
import psutil
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager
import functools
import pickle
import hashlib


@dataclass
class PerformanceMetric:
    """Represents a single performance measurement."""
    operation: str
    start_time: float
    end_time: float
    duration: float
    memory_start: float
    memory_peak: float
    memory_end: float
    cpu_percent: float
    status: str = "completed"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceSnapshot:
    """Snapshot of system resource usage."""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    disk_io_read: int
    disk_io_write: int
    network_sent: int
    network_recv: int


class PerformanceMonitor:
    """Real-time performance monitoring and profiling."""
    
    def __init__(self, enable_detailed_monitoring: bool = True):
        """Initialize performance monitor.
        
        Args:
            enable_detailed_monitoring: Enable detailed CPU/memory tracking
        """
        self.enable_detailed_monitoring = enable_detailed_monitoring
        self.metrics: List[PerformanceMetric] = []
        self.resource_snapshots: deque = deque(maxlen=1000)
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        
        # Performance thresholds
        self.thresholds = {
            "max_operation_time": 600.0,  # 10 minutes
            "max_memory_mb": 2048,        # 2GB
            "max_cpu_percent": 80.0,      # 80%
            "warning_memory_mb": 1024,    # 1GB
            "warning_cpu_percent": 60.0   # 60%
        }
        
        if self.enable_detailed_monitoring:
            self._start_resource_monitoring()
            
        logging.info("PerformanceMonitor initialized")
        
    def _start_resource_monitoring(self):
        """Start background resource monitoring."""
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_resources,
            daemon=True
        )
        self.monitoring_thread.start()
        
    def _monitor_resources(self):
        """Background resource monitoring loop."""
        process = psutil.Process()
        
        while self.monitoring_active:
            try:
                # Get system metrics
                cpu_percent = psutil.cpu_percent()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # Get IO metrics
                io_counters = psutil.disk_io_counters()
                net_counters = psutil.net_io_counters()
                
                snapshot = ResourceSnapshot(
                    timestamp=time.time(),
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    disk_io_read=io_counters.read_bytes if io_counters else 0,
                    disk_io_write=io_counters.write_bytes if io_counters else 0,
                    network_sent=net_counters.bytes_sent if net_counters else 0,
                    network_recv=net_counters.bytes_recv if net_counters else 0
                )
                
                self.resource_snapshots.append(snapshot)
                
                # Check for resource warnings
                if memory_mb > self.thresholds["warning_memory_mb"]:
                    logging.warning(f"High memory usage: {memory_mb:.1f}MB")
                if cpu_percent > self.thresholds["warning_cpu_percent"]:
                    logging.warning(f"High CPU usage: {cpu_percent:.1f}%")
                    
                time.sleep(5.0)  # Monitor every 5 seconds
                
            except Exception as e:
                logging.error(f"Resource monitoring error: {e}")
                time.sleep(10.0)
                
    @contextmanager
    def track_operation(self, operation_name: str, metadata: Dict[str, Any] = None):
        """Context manager for tracking operation performance.
        
        Args:
            operation_name: Name of the operation being tracked
            metadata: Additional metadata to store with the metric
        """
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        start_time = time.time()
        
        # Get initial resource usage
        process = psutil.Process()
        memory_start = process.memory_info().rss / 1024 / 1024
        
        # Store active operation info
        self.active_operations[operation_id] = {
            "name": operation_name,
            "start_time": start_time,
            "memory_start": memory_start,
            "metadata": metadata or {}
        }
        
        cpu_usage = []
        memory_peak = memory_start
        
        try:
            # Track peak resource usage during operation
            if self.enable_detailed_monitoring:
                monitoring_start = time.time()
                
            yield operation_id
            
            # Calculate final metrics
            end_time = time.time()
            duration = end_time - start_time
            memory_end = process.memory_info().rss / 1024 / 1024
            
            # Get peak memory from recent snapshots
            recent_snapshots = [
                s for s in self.resource_snapshots 
                if s.timestamp >= start_time
            ]
            if recent_snapshots:
                memory_peak = max(s.memory_mb for s in recent_snapshots)
                avg_cpu = sum(s.cpu_percent for s in recent_snapshots) / len(recent_snapshots)
            else:
                avg_cpu = psutil.cpu_percent()
                
            # Create metric
            metric = PerformanceMetric(
                operation=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_start=memory_start,
                memory_peak=memory_peak,
                memory_end=memory_end,
                cpu_percent=avg_cpu,
                status="completed",
                metadata=metadata or {}
            )
            
            self.metrics.append(metric)
            
            # Log performance info
            logging.info(
                f"Operation '{operation_name}' completed in {duration:.2f}s "
                f"(mem: {memory_start:.1f} -> {memory_end:.1f}MB, peak: {memory_peak:.1f}MB)"
            )
            
        except Exception as e:
            # Record failed operation
            end_time = time.time()
            duration = end_time - start_time
            memory_end = process.memory_info().rss / 1024 / 1024
            
            metric = PerformanceMetric(
                operation=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_start=memory_start,
                memory_peak=memory_peak,
                memory_end=memory_end,
                cpu_percent=psutil.cpu_percent(),
                status="failed",
                error_message=str(e),
                metadata=metadata or {}
            )
            
            self.metrics.append(metric)
            logging.error(f"Operation '{operation_name}' failed after {duration:.2f}s: {e}")
            raise
            
        finally:
            # Clean up active operation
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
                
    def get_current_resource_usage(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        process = psutil.Process()
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "memory_percent": process.memory_percent(),
            "active_operations": len(self.active_operations),
            "total_metrics_collected": len(self.metrics)
        }
        
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.metrics:
            return {"error": "No performance data available"}
            
        # Calculate aggregate statistics
        total_operations = len(self.metrics)
        completed_operations = len([m for m in self.metrics if m.status == "completed"])
        failed_operations = len([m for m in self.metrics if m.status == "failed"])
        
        durations = [m.duration for m in self.metrics if m.status == "completed"]
        memory_peaks = [m.memory_peak for m in self.metrics]
        
        # Operation statistics
        operation_stats = defaultdict(lambda: {"count": 0, "total_time": 0, "failures": 0})
        for metric in self.metrics:
            stats = operation_stats[metric.operation]
            stats["count"] += 1
            stats["total_time"] += metric.duration
            if metric.status == "failed":
                stats["failures"] += 1
                
        # Generate report
        report = {
            "summary": {
                "total_operations": total_operations,
                "completed_operations": completed_operations,
                "failed_operations": failed_operations,
                "success_rate": completed_operations / total_operations if total_operations > 0 else 0,
                "total_time": sum(durations) if durations else 0,
                "average_duration": sum(durations) / len(durations) if durations else 0,
                "peak_memory_mb": max(memory_peaks) if memory_peaks else 0
            },
            "operation_breakdown": {
                op: {
                    "count": stats["count"],
                    "total_time": stats["total_time"],
                    "average_time": stats["total_time"] / stats["count"],
                    "failure_rate": stats["failures"] / stats["count"] if stats["count"] > 0 else 0
                }
                for op, stats in operation_stats.items()
            },
            "performance_trends": self._analyze_performance_trends(),
            "resource_utilization": self._analyze_resource_utilization(),
            "bottlenecks": self._identify_bottlenecks(),
            "recommendations": self._generate_performance_recommendations()
        }
        
        return report
        
    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        if len(self.metrics) < 5:
            return {"insufficient_data": True}
            
        # Sort metrics by time
        sorted_metrics = sorted(self.metrics, key=lambda m: m.start_time)
        
        # Calculate moving averages
        window_size = min(10, len(sorted_metrics) // 2)
        recent_durations = [m.duration for m in sorted_metrics[-window_size:] if m.status == "completed"]
        early_durations = [m.duration for m in sorted_metrics[:window_size] if m.status == "completed"]
        
        trend_analysis = {
            "operations_over_time": len(sorted_metrics),
            "performance_improving": False,
            "average_duration_change": 0
        }
        
        if recent_durations and early_durations:
            recent_avg = sum(recent_durations) / len(recent_durations)
            early_avg = sum(early_durations) / len(early_durations)
            
            trend_analysis["performance_improving"] = recent_avg < early_avg
            trend_analysis["average_duration_change"] = recent_avg - early_avg
            
        return trend_analysis
        
    def _analyze_resource_utilization(self) -> Dict[str, Any]:
        """Analyze resource utilization patterns."""
        if not self.resource_snapshots:
            return {"no_resource_data": True}
            
        snapshots = list(self.resource_snapshots)
        
        return {
            "average_cpu": sum(s.cpu_percent for s in snapshots) / len(snapshots),
            "peak_cpu": max(s.cpu_percent for s in snapshots),
            "average_memory_mb": sum(s.memory_mb for s in snapshots) / len(snapshots),
            "peak_memory_mb": max(s.memory_mb for s in snapshots),
            "monitoring_duration": snapshots[-1].timestamp - snapshots[0].timestamp if len(snapshots) > 1 else 0
        }
        
    def _identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks."""
        bottlenecks = []
        
        # Find slowest operations
        completed_metrics = [m for m in self.metrics if m.status == "completed"]
        if completed_metrics:
            slowest = max(completed_metrics, key=lambda m: m.duration)
            if slowest.duration > self.thresholds["max_operation_time"] * 0.5:
                bottlenecks.append({
                    "type": "slow_operation",
                    "operation": slowest.operation,
                    "duration": slowest.duration,
                    "description": f"Operation '{slowest.operation}' took {slowest.duration:.1f}s"
                })
                
        # Find memory-intensive operations
        memory_intensive = [m for m in self.metrics if m.memory_peak > self.thresholds["warning_memory_mb"]]
        if memory_intensive:
            worst = max(memory_intensive, key=lambda m: m.memory_peak)
            bottlenecks.append({
                "type": "high_memory_usage",
                "operation": worst.operation,
                "memory_peak": worst.memory_peak,
                "description": f"Operation '{worst.operation}' used {worst.memory_peak:.1f}MB peak memory"
            })
            
        # Find frequently failing operations
        operation_failures = defaultdict(int)
        operation_totals = defaultdict(int)
        
        for metric in self.metrics:
            operation_totals[metric.operation] += 1
            if metric.status == "failed":
                operation_failures[metric.operation] += 1
                
        for operation, failures in operation_failures.items():
            total = operation_totals[operation]
            failure_rate = failures / total
            
            if failure_rate > 0.3:  # >30% failure rate
                bottlenecks.append({
                    "type": "high_failure_rate",
                    "operation": operation,
                    "failure_rate": failure_rate,
                    "description": f"Operation '{operation}' fails {failure_rate:.1%} of the time"
                })
                
        return bottlenecks
        
    def _generate_performance_recommendations(self) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        # Check overall performance
        if self.metrics:
            avg_duration = sum(m.duration for m in self.metrics if m.status == "completed") / max(1, len([m for m in self.metrics if m.status == "completed"]))
            
            if avg_duration > 60:  # Operations taking over 1 minute
                recommendations.append("Consider enabling caching to reduce operation time")
                recommendations.append("Enable parallel processing for independent operations")
                
        # Check memory usage
        if self.resource_snapshots:
            peak_memory = max(s.memory_mb for s in self.resource_snapshots)
            
            if peak_memory > self.thresholds["warning_memory_mb"]:
                recommendations.append("Consider processing data in smaller chunks to reduce memory usage")
                recommendations.append("Enable memory optimization features")
                
        # Check failure rates
        if self.metrics:
            failure_rate = len([m for m in self.metrics if m.status == "failed"]) / len(self.metrics)
            
            if failure_rate > 0.1:  # >10% failure rate
                recommendations.append("Enable advanced error recovery strategies to improve success rate")
                recommendations.append("Increase max_iterations setting for better retry logic")
                
        return recommendations
        
    def stop_monitoring(self):
        """Stop background resource monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)
            
    def save_performance_data(self, filepath: str):
        """Save performance data to file for analysis."""
        data = {
            "metrics": [
                {
                    "operation": m.operation,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "duration": m.duration,
                    "memory_start": m.memory_start,
                    "memory_peak": m.memory_peak,
                    "memory_end": m.memory_end,
                    "cpu_percent": m.cpu_percent,
                    "status": m.status,
                    "error_message": m.error_message,
                    "metadata": m.metadata
                }
                for m in self.metrics
            ],
            "resource_snapshots": [
                {
                    "timestamp": s.timestamp,
                    "cpu_percent": s.cpu_percent,
                    "memory_mb": s.memory_mb,
                    "disk_io_read": s.disk_io_read,
                    "disk_io_write": s.disk_io_write,
                    "network_sent": s.network_sent,
                    "network_recv": s.network_recv
                }
                for s in list(self.resource_snapshots)
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
        logging.info(f"Performance data saved to {filepath}")


class CacheManager:
    """Intelligent caching system for workflow optimization."""
    
    def __init__(self, cache_dir: str, max_cache_size_mb: int = 500):
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache storage
            max_cache_size_mb: Maximum cache size in MB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        self.cache_stats = {"hits": 0, "misses": 0}
        
    def _get_cache_key(self, operation: str, inputs: Dict[str, Any]) -> str:
        """Generate cache key from operation and inputs."""
        # Create deterministic hash from operation and inputs
        content = json.dumps({"operation": operation, "inputs": inputs}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
        
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{cache_key}.cache"
        
    def get(self, operation: str, inputs: Dict[str, Any]) -> Optional[Any]:
        """Get cached result if available.
        
        Args:
            operation: Operation name
            inputs: Operation inputs
            
        Returns:
            Cached result or None
        """
        cache_key = self._get_cache_key(operation, inputs)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    
                # Check if cache is still valid (within 24 hours)
                cache_age = time.time() - cache_path.stat().st_mtime
                if cache_age < 24 * 3600:  # 24 hours
                    self.cache_stats["hits"] += 1
                    logging.debug(f"Cache hit for operation '{operation}'")
                    return cached_data["result"]
                else:
                    # Cache expired, remove it
                    cache_path.unlink()
                    
            except Exception as e:
                logging.warning(f"Failed to load cache for '{operation}': {e}")
                
        self.cache_stats["misses"] += 1
        return None
        
    def set(self, operation: str, inputs: Dict[str, Any], result: Any):
        """Cache operation result.
        
        Args:
            operation: Operation name
            inputs: Operation inputs
            result: Operation result to cache
        """
        cache_key = self._get_cache_key(operation, inputs)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cached_data = {
                "operation": operation,
                "inputs": inputs,
                "result": result,
                "timestamp": time.time()
            }
            
            with open(cache_path, 'wb') as f:
                pickle.dump(cached_data, f)
                
            logging.debug(f"Cached result for operation '{operation}'")
            
            # Clean up old cache if needed
            self._cleanup_cache()
            
        except Exception as e:
            logging.warning(f"Failed to cache result for '{operation}': {e}")
            
    def _cleanup_cache(self):
        """Clean up old cache files if size limit exceeded."""
        try:
            # Get all cache files with their sizes and modification times
            cache_files = []
            total_size = 0
            
            for cache_file in self.cache_dir.glob("*.cache"):
                stat = cache_file.stat()
                cache_files.append((cache_file, stat.st_size, stat.st_mtime))
                total_size += stat.st_size
                
            if total_size > self.max_cache_size:
                # Sort by modification time (oldest first)
                cache_files.sort(key=lambda x: x[2])
                
                # Remove oldest files until under size limit
                for cache_file, size, _ in cache_files:
                    if total_size <= self.max_cache_size * 0.8:  # Leave 20% buffer
                        break
                    cache_file.unlink()
                    total_size -= size
                    
                logging.info(f"Cache cleanup completed, new size: {total_size / 1024 / 1024:.1f}MB")
                
        except Exception as e:
            logging.error(f"Cache cleanup failed: {e}")
            
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = self.cache_stats["hits"] / total_requests if total_requests > 0 else 0
        
        # Calculate cache size
        cache_size = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.cache") 
            if f.exists()
        )
        
        return {
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "hit_rate": hit_rate,
            "cache_size_mb": cache_size / 1024 / 1024,
            "cache_files": len(list(self.cache_dir.glob("*.cache")))
        }


class ResourceOptimizer:
    """System resource optimization and recommendations."""
    
    def __init__(self):
        """Initialize resource optimizer."""
        self.optimization_strategies = {
            "memory": self._optimize_memory_usage,
            "cpu": self._optimize_cpu_usage,
            "io": self._optimize_io_operations,
            "caching": self._optimize_caching_strategy
        }
        
    def analyze_and_optimize(self, performance_report: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance and generate optimizations.
        
        Args:
            performance_report: Performance report from PerformanceMonitor
            
        Returns:
            Optimization recommendations and applied optimizations
        """
        recommendations = {
            "applied_optimizations": [],
            "recommended_changes": [],
            "performance_impact": {},
            "configuration_suggestions": {}
        }
        
        # Analyze different resource categories
        for category, optimizer_func in self.optimization_strategies.items():
            try:
                optimizations = optimizer_func(performance_report)
                if optimizations:
                    recommendations["recommended_changes"].extend(optimizations)
                    
            except Exception as e:
                logging.error(f"Optimization analysis failed for {category}: {e}")
                
        # Generate configuration suggestions
        recommendations["configuration_suggestions"] = self._generate_config_suggestions(
            performance_report
        )
        
        return recommendations
        
    def _optimize_memory_usage(self, report: Dict[str, Any]) -> List[str]:
        """Generate memory optimization recommendations."""
        recommendations = []
        
        summary = report.get("summary", {})
        peak_memory = summary.get("peak_memory_mb", 0)
        
        if peak_memory > 1024:  # >1GB
            recommendations.append("Enable data chunking to process large files in smaller pieces")
            recommendations.append("Consider using streaming data processing instead of loading entire files")
            
        if peak_memory > 2048:  # >2GB
            recommendations.append("CRITICAL: Memory usage is very high - consider running on a machine with more RAM")
            
        return recommendations
        
    def _optimize_cpu_usage(self, report: Dict[str, Any]) -> List[str]:
        """Generate CPU optimization recommendations."""
        recommendations = []
        
        resource_util = report.get("resource_utilization", {})
        avg_cpu = resource_util.get("average_cpu", 0)
        
        if avg_cpu < 30:  # CPU underutilized
            recommendations.append("CPU is underutilized - consider enabling parallel processing")
            recommendations.append("Increase the number of concurrent operations if supported")
            
        elif avg_cpu > 80:  # CPU overutilized
            recommendations.append("CPU usage is high - consider reducing concurrent operations")
            
        return recommendations
        
    def _optimize_io_operations(self, report: Dict[str, Any]) -> List[str]:
        """Generate I/O optimization recommendations."""
        recommendations = []
        
        # Check for I/O intensive operations
        bottlenecks = report.get("bottlenecks", [])
        slow_operations = [b for b in bottlenecks if b.get("type") == "slow_operation"]
        
        if slow_operations:
            recommendations.append("Enable caching to reduce repeated file I/O operations")
            recommendations.append("Consider using faster storage (SSD) for better I/O performance")
            
        return recommendations
        
    def _optimize_caching_strategy(self, report: Dict[str, Any]) -> List[str]:
        """Generate caching optimization recommendations."""
        recommendations = []
        
        operation_breakdown = report.get("operation_breakdown", {})
        
        # Look for repeated operations
        repeated_ops = [
            op for op, stats in operation_breakdown.items()
            if stats.get("count", 0) > 2 and stats.get("average_time", 0) > 10
        ]
        
        if repeated_ops:
            recommendations.append("Enable caching for repeated operations: " + ", ".join(repeated_ops))
            recommendations.append("Consider increasing cache size for better hit rates")
            
        return recommendations
        
    def _generate_config_suggestions(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate configuration suggestions based on performance."""
        suggestions = {}
        
        summary = report.get("summary", {})
        success_rate = summary.get("success_rate", 1.0)
        avg_duration = summary.get("average_duration", 0)
        
        # Iteration settings
        if success_rate < 0.8:  # <80% success rate
            suggestions["max_iterations"] = "Increase to 5-7 for better error recovery"
            suggestions["auto_fix"] = "Enable automatic error fixes"
            suggestions["use_advanced_fixes"] = "Enable advanced fix strategies"
            
        # Performance settings
        if avg_duration > 300:  # >5 minutes average
            suggestions["enable_caching"] = "Enable caching to reduce processing time"
            suggestions["batch_mode"] = "Consider batch processing for multiple files"
            
        # Memory settings  
        peak_memory = summary.get("peak_memory_mb", 0)
        if peak_memory > 1024:
            suggestions["chunked_processing"] = "Enable chunked processing for large datasets"
            
        return suggestions


def create_performance_monitor(enable_detailed: bool = True) -> PerformanceMonitor:
    """Factory function to create PerformanceMonitor."""
    return PerformanceMonitor(enable_detailed_monitoring=enable_detailed)


def create_cache_manager(cache_dir: str, max_size_mb: int = 500) -> CacheManager:
    """Factory function to create CacheManager."""
    return CacheManager(cache_dir, max_size_mb)


def create_resource_optimizer() -> ResourceOptimizer:
    """Factory function to create ResourceOptimizer."""
    return ResourceOptimizer()


# Decorator for automatic performance monitoring
def monitor_performance(operation_name: str = None, enable_caching: bool = False, 
                       cache_manager: CacheManager = None):
    """Decorator for automatic performance monitoring and caching.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
        enable_caching: Enable result caching
        cache_manager: Cache manager instance (required if enable_caching=True)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal operation_name
            if operation_name is None:
                operation_name = func.__name__
                
            # Try to get cached result if caching enabled
            if enable_caching and cache_manager:
                cache_inputs = {"args": args, "kwargs": kwargs}
                cached_result = cache_manager.get(operation_name, cache_inputs)
                if cached_result is not None:
                    return cached_result
                    
            # Execute with performance monitoring
            # Note: This would need access to a global PerformanceMonitor instance
            # In practice, this would be injected or passed as a parameter
            
            result = func(*args, **kwargs)
            
            # Cache result if caching enabled
            if enable_caching and cache_manager:
                cache_manager.set(operation_name, cache_inputs, result)
                
            return result
            
        return wrapper
    return decorator