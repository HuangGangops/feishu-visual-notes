#!/usr/bin/env python3
"""Run local deterministic tests for all bundled diagram types and variants."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SPECS = [
    ("flow-horizontal", "horizontal", {"type": "flow", "variant": "auto", "title": "项目流程", "nodes": ["需求", "数据", "评测", "报告"]}),
    ("flow-vertical", "vertical", {"type": "flow", "variant": "auto", "title": "长流程", "nodes": ["一", "二", "三", "四", "五", "六"]}),
    ("flow-loop", "loop", {"type": "flow", "variant": "auto", "closed_loop": True, "title": "改进闭环", "nodes": ["发现问题", "分析原因", "制定方案", "验证效果"]}),
    ("map-radial", "radial", {"type": "knowledge-map", "variant": "auto", "title": "知识地图", "center": "核心主题", "branches": ["概念", "方法", "流程", "案例"]}),
    ("map-layered", "layered", {"type": "knowledge-map", "variant": "auto", "title": "知识层级", "levels": [[{"id": "root", "title": "课程"}], [{"title": "理论", "parent": "root"}, {"title": "实践", "parent": "root"}]]}),
    ("timeline-linear", "linear", {"type": "timeline", "variant": "auto", "title": "短周期", "events": [{"title": "启动", "meta": "第1周"}, {"title": "执行", "meta": "第2周"}, {"title": "交付", "meta": "第3周"}]}),
    ("timeline-alternating", "alternating", {"type": "timeline", "variant": "auto", "title": "完整周期", "events": [{"title": f"阶段{i + 1}", "meta": f"第{i + 1}周"} for i in range(5)]}),
    ("matrix", "comparison", {"type": "matrix", "variant": "auto", "title": "方法对比", "columns": ["维度", "方案A", "方案B"], "rows": [["成本", "低", "中"], ["效果", "中", "高"]]}),
    ("decision", "branch", {"type": "decision", "variant": "auto", "title": "决策路径", "question": {"title": "数据是否充足？", "body": "判断证据基础"}, "options": [{"title": "充足", "body": "进入定量评测"}, {"title": "不足", "body": "补充样本"}]}),
    ("swimlane", "lanes", {"type": "swimlane", "variant": "auto", "title": "协作流程", "lanes": [{"title": "业务方", "steps": ["提出需求", "验收结果"]}, {"title": "评测方", "steps": ["设计方案", "执行评测", "输出报告"]}]}),
    ("funnel", "descending", {"type": "funnel", "variant": "auto", "title": "样本筛选", "stages": ["原始数据", "规则过滤", "人工复核", "有效样本"]}),
    ("quadrant", "2x2", {"type": "quadrant", "variant": "auto", "title": "任务优先级", "quadrants": [{"title": "重要紧急", "body": "立即处理"}, {"title": "重要不紧急", "body": "计划推进"}, {"title": "不重要紧急", "body": "授权处理"}, {"title": "不重要不紧急", "body": "减少投入"}]}),
    ("cause-effect", "fishbone", {"type": "cause-effect", "variant": "auto", "title": "问题归因", "effect": {"title": "评测结果偏低", "body": "需要定位根因"}, "causes": [{"title": "数据", "items": ["覆盖不足", "分布偏差"]}, {"title": "规则", "items": ["阈值不清"]}, {"title": "执行", "items": ["理解不一致"]}, {"title": "工具", "items": ["记录缺失"]}]}),
]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    builder = script_dir / "build_feishu_diagram.py"
    validator = script_dir / "validate_svg_layout.py"
    highlight_auditor = script_dir / "audit_highlight_coverage.py"
    diagram_scorer = script_dir / "score_diagram_candidates.py"
    batch_auditor = script_dir / "audit_batch_manifest.py"
    preflight = script_dir / "preflight.py"
    visual_validator = script_dir / "validate_visual_source.py"
    results = []

    with tempfile.TemporaryDirectory(prefix="feishu-visual-notes-") as temp_dir:
        temp = Path(temp_dir)
        for name, expected_variant, spec in SPECS:
            spec_path = temp / f"{name}.json"
            svg_path = temp / f"{name}.svg"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

            build = run([sys.executable, str(builder), "--input", str(spec_path), "--output", str(svg_path)])
            if build.returncode != 0:
                print(build.stderr, file=sys.stderr)
                return 1
            build_result = json.loads(build.stdout)
            if build_result.get("variant") != expected_variant:
                print(f"{name}: expected {expected_variant}, got {build_result.get('variant')}", file=sys.stderr)
                return 1

            validate = run([sys.executable, str(validator), "--input", str(svg_path), "--strict"])
            if validate.returncode != 0:
                print(validate.stdout or validate.stderr, file=sys.stderr)
                return 1
            validation = json.loads(validate.stdout)
            results.append({"name": name, "variant": expected_variant, "warnings": len(validation["warnings"])})

        content_path = temp / "highlight-content.xml"
        inventory_path = temp / "highlight-inventory.json"
        content_path.write_text(
            '<p>处理课堂资料时，需要<span background-color="light-yellow">完整识别课件</span>并核对所有页面、图表和公式。'
            '确认内容覆盖没有缺口以后，按照课程主线进行<span background-color="light-yellow">统一框架整理</span>，'
            '同时保留原始定义、案例和结论，便于后续复习与核查。</p>',
            encoding="utf-8",
        )
        inventory_path.write_text(
            json.dumps(
                {
                    "key_points": [
                        {"section": "流程", "highlight": "完整识别课件"},
                        {"section": "流程", "highlight": "统一框架整理"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        highlight_ok = run(
            [sys.executable, str(highlight_auditor), "--content", str(content_path), "--inventory", str(inventory_path), "--strict"]
        )
        if highlight_ok.returncode != 0:
            print(highlight_ok.stdout or highlight_ok.stderr, file=sys.stderr)
            return 1
        results.append({"name": "highlight-coverage-pass", "warnings": 0})

        inventory_path.write_text(
            json.dumps({"key_points": ["完整识别课件", "统一框架整理", "遗漏重点"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        highlight_fail = run(
            [sys.executable, str(highlight_auditor), "--content", str(content_path), "--inventory", str(inventory_path), "--strict"]
        )
        if highlight_fail.returncode == 0:
            print("Highlight coverage auditor accepted a missing key point.", file=sys.stderr)
            return 1
        results.append({"name": "highlight-coverage-rejects-missing", "warnings": 0})

        visual_ok = run([sys.executable, str(visual_validator), "--input", str(content_path), "--minimum-highlights", "2"])
        if visual_ok.returncode != 0:
            print(visual_ok.stdout or visual_ok.stderr, file=sys.stderr)
            return 1
        results.append({"name": "visual-source-validation", "warnings": 0})

        score_path = temp / "diagram-score.json"
        score_path.write_text(
            json.dumps(
                {"question": "不同角色如何交接？", "signals": ["roles", "handoffs", "ordered_steps"]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        score = run([sys.executable, str(diagram_scorer), "--input", str(score_path)])
        if score.returncode != 0 or json.loads(score.stdout)["recommended"]["type"] != "swimlane":
            print(score.stdout or score.stderr, file=sys.stderr)
            return 1
        results.append({"name": "diagram-scoring", "recommended": "swimlane", "warnings": 0})

        (temp / "batch-001.json").write_text("{}", encoding="utf-8")
        (temp / "batch-002.json").write_text("{}", encoding="utf-8")
        manifest_path = temp / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "total_pages": 6,
                    "batches": [
                        {"id": "001", "start": 1, "end": 3, "status": "complete", "output": "batch-001.json"},
                        {"id": "002", "start": 4, "end": 6, "status": "complete", "output": "batch-002.json"},
                    ],
                    "uncertain_pages": [2],
                    "important_visual_pages": [5],
                    "original_resolution_pages": [2, 5],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest_ok = run([sys.executable, str(batch_auditor), "--input", str(manifest_path), "--strict"])
        if manifest_ok.returncode != 0:
            print(manifest_ok.stdout or manifest_ok.stderr, file=sys.stderr)
            return 1
        results.append({"name": "batch-manifest-pass", "warnings": 0})

        manifest_path.write_text(
            json.dumps(
                {
                    "total_pages": 6,
                    "batches": [
                        {"id": "001", "start": 1, "end": 4, "status": "complete", "output": "batch-001.json"},
                        {"id": "002", "start": 4, "end": 5, "status": "complete", "output": "batch-002.json"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest_fail = run([sys.executable, str(batch_auditor), "--input", str(manifest_path), "--strict"])
        if manifest_fail.returncode == 0:
            print("Batch manifest auditor accepted missing or overlapping pages.", file=sys.stderr)
            return 1
        results.append({"name": "batch-manifest-rejects-gaps", "warnings": 0})

        preflight_ok = run([sys.executable, str(preflight), "--offline", "--json"])
        if preflight_ok.returncode != 0 or not json.loads(preflight_ok.stdout).get("ok"):
            print(preflight_ok.stdout or preflight_ok.stderr, file=sys.stderr)
            return 1
        results.append({"name": "offline-preflight", "warnings": 0})

    print(json.dumps({"ok": True, "cases": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
