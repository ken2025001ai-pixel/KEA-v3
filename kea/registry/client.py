"""Registry 客户端 — 管理 OntologySkill 的注册、查询和版本控制.

Registry 是一个本地文件系统仓库（最小可用版），
存储结构：
registry/
  ├── catalog.yml          # 资产目录索引
  ├── assets/
  │   ├── {asset_id}/
  │   │   ├── v1.0.0/
  │   │   │   ├── skill.py
  │   │   │   ├── meta.yml
  │   │   │   └── signature.sha256
  │   │   └── v1.1.0/
  │   └── ...
  └── versions/
      └── {asset_id}_latest -> ../assets/{asset_id}/vX.Y.Z
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any



@dataclass
class AssetRef:
    """资产引用."""

    asset_id: str
    version: str
    kind: str = ""
    path: str = ""


@dataclass
class Asset:
    """Registry 中的资产."""

    asset_id: str
    version: str
    kind: str
    code: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    signature: str = ""


class RegistryClient:
    """Registry 客户端.

    最小可用版实现，使用本地文件系统存储。
    """

    def __init__(self, registry_dir: str = "registry") -> None:
        self.registry_dir = Path(registry_dir)
        self.assets_dir = self.registry_dir / "assets"
        self.catalog_file = self.registry_dir / "catalog.json"

        # 确保目录存在
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register(self, asset: Asset) -> AssetRef:
        """注册资产到 Registry.

        Args:
            asset: 要注册的资产

        Returns:
            资产引用
        """
        # 计算签名
        asset.signature = self._sign(asset.code)

        # 创建版本目录
        asset_dir = self.assets_dir / asset.asset_id / asset.version
        asset_dir.mkdir(parents=True, exist_ok=True)

        # 写入代码
        code_file = asset_dir / "skill.py"
        code_file.write_text(asset.code, encoding="utf-8")

        # 写入元数据
        meta_file = asset_dir / "meta.json"
        meta_content = {
            "asset_id": asset.asset_id,
            "version": asset.version,
            "kind": asset.kind,
            "signature": asset.signature,
            "provenance": asset.meta.get("provenance", {}),
            "runtime": asset.meta.get("runtime", {}),
            "dependencies": asset.meta.get("dependencies", []),
            "preconditions": asset.meta.get("preconditions", []),
            "postconditions": asset.meta.get("postconditions", []),
        }
        meta_file.write_text(json.dumps(meta_content, ensure_ascii=False, indent=2), encoding="utf-8")

        # 写入签名文件
        sig_file = asset_dir / "signature.sha256"
        sig_file.write_text(asset.signature, encoding="utf-8")

        # 更新 latest 软链接/标记
        latest_file = self.assets_dir / asset.asset_id / "_latest"
        latest_file.write_text(asset.version, encoding="utf-8")

        # 更新目录
        self._update_catalog(asset)

        return AssetRef(
            asset_id=asset.asset_id,
            version=asset.version,
            kind=asset.kind,
            path=str(asset_dir),
        )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def load(self, asset_id: str, version: str = "") -> Asset | None:
        """加载指定资产.

        Args:
            asset_id: 资产 ID
            version: 版本号，空字符串表示最新版本

        Returns:
            资产对象，不存在返回 None
        """
        if not version:
            version = self._get_latest_version(asset_id)
            if not version:
                return None

        asset_dir = self.assets_dir / asset_id / version
        if not asset_dir.exists():
            return None

        code_file = asset_dir / "skill.py"
        meta_file = asset_dir / "meta.yml"
        sig_file = asset_dir / "signature.sha256"

        if not code_file.exists():
            return None

        code = code_file.read_text(encoding="utf-8")
        meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        signature = sig_file.read_text(encoding="utf-8").strip() if sig_file.exists() else ""

        return Asset(
            asset_id=asset_id,
            version=version,
            kind=meta.get("kind", "skill"),
            code=code,
            meta=meta,
            signature=signature,
        )

    def list_versions(self, asset_id: str) -> list[str]:
        """列出资产的所有版本."""
        asset_dir = self.assets_dir / asset_id
        if not asset_dir.exists():
            return []

        versions = []
        for d in asset_dir.iterdir():
            if d.is_dir() and d.name != "_latest":
                versions.append(d.name)
        return sorted(versions, key=self._version_key)

    def list_assets(self, kind: str = "") -> list[AssetRef]:
        """列出所有资产."""
        refs = []
        for asset_dir in self.assets_dir.iterdir():
            if not asset_dir.is_dir():
                continue
            asset_id = asset_dir.name
            version = self._get_latest_version(asset_id)
            if version:
                meta_file = asset_dir / version / "meta.json"
                asset_kind = ""
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    asset_kind = meta.get("kind", "")
                if not kind or kind == asset_kind:
                    refs.append(AssetRef(
                        asset_id=asset_id,
                        version=version,
                        kind=asset_kind,
                        path=str(asset_dir / version),
                    ))
        return refs

    # ------------------------------------------------------------------
    # 签名验证
    # ------------------------------------------------------------------

    def verify(self, asset_id: str, version: str = "") -> bool:
        """验证资产签名."""
        asset = self.load(asset_id, version)
        if not asset:
            return False
        expected = self._sign(asset.code)
        return expected == asset.signature

    # ------------------------------------------------------------------
    # 删除/回滚
    # ------------------------------------------------------------------

    def rollback(self, asset_id: str, to_version: str) -> bool:
        """回滚资产到指定版本."""
        asset_dir = self.assets_dir / asset_id / to_version
        if not asset_dir.exists():
            return False

        latest_file = self.assets_dir / asset_id / "_latest"
        latest_file.write_text(to_version, encoding="utf-8")
        return True

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _sign(self, code: str) -> str:
        """计算代码的 SHA256 签名."""
        return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]

    def _get_latest_version(self, asset_id: str) -> str:
        """获取资产的最新版本."""
        latest_file = self.assets_dir / asset_id / "_latest"
        if latest_file.exists():
            return latest_file.read_text(encoding="utf-8").strip()
        return ""

    def _version_key(self, version: str) -> tuple[int, ...]:
        """版本号排序键."""
        parts = version.lstrip("v").split(".")
        return tuple(int(p) if p.isdigit() else 0 for p in parts)

    def _update_catalog(self, asset: Asset) -> None:
        """更新目录索引."""
        catalog = self._load_catalog()

        # 查找或创建条目
        entry = None
        for e in catalog.get("assets", []):
            if e.get("asset_id") == asset.asset_id:
                entry = e
                break

        if entry is None:
            entry = {"asset_id": asset.asset_id, "versions": []}
            catalog.setdefault("assets", []).append(entry)

        if asset.version not in entry.get("versions", []):
            entry.setdefault("versions", []).append(asset.version)
            entry["versions"] = sorted(entry["versions"], key=self._version_key)

        entry["latest"] = asset.version
        entry["kind"] = asset.kind

        self.catalog_file.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_catalog(self) -> dict[str, Any]:
        """加载目录."""
        if self.catalog_file.exists():
            return json.loads(self.catalog_file.read_text(encoding="utf-8")) or {}
        return {"assets": []}
