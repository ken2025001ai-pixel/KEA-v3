"""OntologySkill Runtime — 执行器.

负责加载 OntologySkill、参数校验、前置/后置检查、审计日志。
最小可用版：直接 Python 函数调用，不依赖 Docker。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from kea.registry.client import RegistryClient

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果."""

    success: bool = False
    data: Any = None
    error: str = ""
    trace: str = ""
    audit_log: list[dict] = field(default_factory=list)
    execution_time_ms: float = 0.0


class SkillExecutor:
    """OntologySkill 执行器."""

    def __init__(self, registry: RegistryClient | None = None) -> None:
        self.registry = registry or RegistryClient()
        self._cache: dict[str, Any] = {}  # 已加载的 Skill 类缓存

    def execute(
        self,
        asset_id: str,
        params: dict[str, Any],
        version: str = "",
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """执行 OntologySkill.

        Args:
            asset_id: 资产 ID
            params: 输入参数
            version: 版本号，空表示最新
            context: 运行时上下文

        Returns:
            执行结果
        """
        import time
        start_time = time.time()

        # 1. 加载资产
        asset = self.registry.load(asset_id, version)
        if not asset:
            return ExecutionResult(success=False, error=f"资产不存在: {asset_id}")

        # 2. 签名校验
        if not self.registry.verify(asset_id, version or asset.version):
            return ExecutionResult(success=False, error="签名校验失败")

        # 3. 加载 Skill 类
        skill_class = self._load_skill_class(asset)
        if not skill_class:
            return ExecutionResult(success=False, error="Skill 类加载失败")

        # 4. 实例化
        instance = skill_class(registry=self.registry, dao=context or {})

        # 5. 执行
        try:
            result_data = instance.execute(**params)
            return ExecutionResult(
                success=True,
                data=result_data,
                audit_log=getattr(instance, "audit_log", []),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except AssertionError as e:
            return ExecutionResult(
                success=False,
                error=f"前置/后置条件不满足: {e}",
                trace=traceback.format_exc(),
                audit_log=getattr(instance, "audit_log", []),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                trace=traceback.format_exc(),
                audit_log=getattr(instance, "audit_log", []),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _load_skill_class(self, asset) -> type | None:
        """动态加载 Skill 类."""
        cache_key = f"{asset.asset_id}:{asset.version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 创建临时模块
        module_name = f"_kea_dynamic_{asset.asset_id}_{asset.version.replace('.', '_')}"

        # 将代码写入临时文件
        tmp_dir = Path(".kea_tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        safe_key = cache_key.replace(":", "_").replace("/", "_")
        tmp_file = tmp_dir / f"{safe_key}.py"
        tmp_file.write_text(asset.code, encoding="utf-8")

        try:
            spec = importlib.util.spec_from_file_location(module_name, tmp_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 查找 Skill 类（类名以 Skill 结尾）
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and name.endswith("Skill"):
                    self._cache[cache_key] = obj
                    return obj

            return None
        except Exception as e:
            logger.error(f"加载 Skill 类失败: {e}")
            return None
