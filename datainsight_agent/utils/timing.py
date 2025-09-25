"""
时间测量工具

提供通用的时间测量装饰器和工具函数，简化组件中的时间测量代码。
"""

import time
from typing import Dict, Any, Callable, Optional
from functools import wraps


def measure_time(node_name: str, state_key: str = "timings") -> Callable:
    """
    时间测量装饰器
    
    Args:
        node_name: 节点名称
        state_key: 状态中存储时间信息的键名
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            # 确保timings列表存在
            state.setdefault(state_key, [])
            
            # 开始计时
            start_perf = time.perf_counter()
            start_time = time.time()
            
            try:
                # 执行原函数
                result = func(self, state, *args, **kwargs)
                
                # 结束计时
                end_perf = time.perf_counter()
                end_time = time.time()
                
                # 记录时间信息
                timing_info = {
                    "node": node_name,
                    "start_ts_ms": int(start_time * 1000),
                    "end_ts_ms": int(end_time * 1000),
                    "duration_ms": int((end_perf - start_perf) * 1000),
                }
                
                # 添加额外的计时信息
                if hasattr(result, 'get'):
                    # 检查是否有跳过信息
                    if result.get('skipped_llm'):
                        timing_info['skipped_llm'] = True
                    elif result.get('skipped_reason'):
                        timing_info['skipped_reason'] = result.get('skipped_reason')
                
                result[state_key].append(timing_info)
                return result
                
            except Exception as e:
                # 即使出错也要记录时间
                end_perf = time.perf_counter()
                end_time = time.time()
                
                timing_info = {
                    "node": node_name,
                    "start_ts_ms": int(start_time * 1000),
                    "end_ts_ms": int(end_time * 1000),
                    "duration_ms": int((end_perf - start_perf) * 1000),
                    "error": str(e)
                }
                
                state[state_key].append(timing_info)
                raise
                
        return wrapper
    return decorator


def add_timing_info(state: Dict[str, Any], node_name: str, 
                   start_perf: float, start_time: float,
                   end_perf: float, end_time: float,
                   **extra_info) -> None:
    """
    手动添加时间信息到状态中
    
    Args:
        state: 状态字典
        node_name: 节点名称
        start_perf: 开始性能计数器
        start_time: 开始时间戳
        end_perf: 结束性能计数器
        end_time: 结束时间戳
        **extra_info: 额外的信息
    """
    state.setdefault("timings", [])
    
    timing_info = {
        "node": node_name,
        "start_ts_ms": int(start_time * 1000),
        "end_ts_ms": int(end_time * 1000),
        "duration_ms": int((end_perf - start_perf) * 1000),
        **extra_info
    }
    
    state["timings"].append(timing_info)


class TimingContext:
    """时间测量上下文管理器"""
    
    def __init__(self, state: Dict[str, Any], node_name: str):
        self.state = state
        self.node_name = node_name
        self.start_perf = None
        self.start_time = None
        
    def __enter__(self):
        self.start_perf = time.perf_counter()
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_perf = time.perf_counter()
        end_time = time.time()
        
        add_timing_info(
            self.state, self.node_name,
            self.start_perf, self.start_time,
            end_perf, end_time
        )
        
        return False  # 不抑制异常
