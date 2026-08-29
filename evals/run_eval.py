"""Prompt 评测：对摘要输出按规则自动判分。

评测集：evals/summary_cases.jsonl（10 条真实电影输入）。
规则（每条 case 全部通过才算 pass）：
  非空 / ≤80字 / 包含片名 / 不复述评分数字 / 不复述评价人数 /
  不含臆测词（"可能""据说"等——prompt 要求只根据给定信息总结）。

两种运行方式：
  离线回放（免费）：python evals/run_eval.py --use-cached
      对 evals/cached_outputs.jsonl 里已保存的历史输出判分，
      没有缓存输出的 case 标记为"未评测"，不假装通过。
  在线实跑（付费）：python evals/run_eval.py --engine handwritten --confirm-paid-run
      --engine lc 用 LangChain 链路；加 --save-cache 把本次输出
      存入缓存文件，供以后离线回放与版本对比。

报告写入 evals/report.json。
"""

import argparse
import json
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

CASES_FILE = EVALS_DIR / "summary_cases.jsonl"
CACHE_FILE = EVALS_DIR / "cached_outputs.jsonl"
REPORT_FILE = EVALS_DIR / "report.json"

HEDGE_WORDS = ("可能", "据说", "大概", "我认为", "应该是", "或许")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_summary(case: dict, output: str) -> dict:
    """纯函数判分：返回逐条规则结果，全部通过才算 pass。"""
    text = (output or "").strip()
    checks = [
        ("非空", bool(text), f"{len(text)}字"),
        ("长度≤80字", 0 < len(text) <= 80, f"{len(text)}字"),
        ("包含片名", case["title"] in text, case["title"]),
        ("不复述评分", str(case["rating"]) not in text, str(case["rating"])),
        (
            "不复述评价人数",
            str(case["rating_count"]) not in text,
            str(case["rating_count"]),
        ),
        (
            "无臆测词",
            not any(word in text for word in HEDGE_WORDS),
            "/".join(word for word in HEDGE_WORDS if word in text) or "-",
        ),
    ]
    return {
        "passed": all(ok for _, ok, _ in checks),
        "checks": [
            {"rule": rule, "ok": ok, "detail": detail}
            for rule, ok, detail in checks
        ],
    }


def evaluate(cases: list[dict], outputs: dict[int, dict]) -> dict:
    """对一批 case 判分。outputs: douban_id -> {output, engine}。"""
    details = []
    evaluated = passed = 0
    for case in cases:
        record = outputs.get(case["douban_id"])
        if record is None:
            details.append({
                "douban_id": case["douban_id"], "title": case["title"],
                "status": "missing",
            })
            continue
        result = score_summary(case, record["output"])
        evaluated += 1
        passed += int(result["passed"])
        details.append({
            "douban_id": case["douban_id"], "title": case["title"],
            "status": "pass" if result["passed"] else "fail",
            "engine": record.get("engine", "unknown"),
            "output": record["output"],
            "checks": result["checks"],
        })
    return {
        "total_cases": len(cases),
        "evaluated": evaluated,
        "passed": passed,
        "pass_rate": round(passed / evaluated, 3) if evaluated else None,
        "missing": len(cases) - evaluated,
        "details": details,
    }


def generate_live(cases: list[dict], engine: str) -> dict[int, dict]:
    """在线生成各 case 的摘要（付费）。"""
    outputs: dict[int, dict] = {}
    if engine == "lc":
        from ai_summary_lc import build_chain

        chain, model = build_chain()
        from ai_summary import build_prompt

        for case in cases:
            text = chain.invoke({"movie_prompt": build_prompt(case)})
            outputs[case["douban_id"]] = {
                "output": text.strip(), "engine": f"lc:{model}",
            }
    else:
        from openai import OpenAI

        from ai_summary import build_prompt, call_with_retry, get_ai_config

        api_key, base_url, model = get_ai_config()
        client = OpenAI(
            api_key=api_key, base_url=base_url, timeout=30.0, max_retries=0
        )
        for case in cases:
            response = call_with_retry(lambda: client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是严谨的电影信息摘要助手。"},
                    {"role": "user", "content": build_prompt(case)},
                ],
                temperature=0.3,
            ))
            outputs[case["douban_id"]] = {
                "output": (response.choices[0].message.content or "").strip(),
                "engine": f"handwritten:{model}",
            }
    return outputs


def print_report(report: dict) -> None:
    print(f"{'状态':<4} {'片名':<10} 摘要/未通过规则")
    for item in report["details"]:
        if item["status"] == "missing":
            print(f"缺失   {item['title']:<10} （无缓存输出，未评测）")
            continue
        failed_rules = "、".join(
            check["rule"] for check in item["checks"] if not check["ok"]
        )
        mark = "通过" if item["status"] == "pass" else "失败"
        note = item["output"][:36] if item["status"] == "pass" else failed_rules
        print(f"{mark:<4} {item['title']:<10} {note}")
    print(
        f"\n合计：{report['total_cases']} 条 case，"
        f"已评测 {report['evaluated']}，通过 {report['passed']}"
        + (
            f"（通过率 {report['pass_rate']:.0%}）"
            if report["pass_rate"] is not None else ""
        )
        + (f"，缺输出未评测 {report['missing']}" if report["missing"] else "")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="摘要 Prompt 评测")
    parser.add_argument("--use-cached", action="store_true",
                        help="对缓存的历史输出判分（免费）")
    parser.add_argument("--engine", choices=["handwritten", "lc"],
                        default="handwritten")
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--save-cache", action="store_true",
                        help="把本次在线输出写入缓存文件")
    args = parser.parse_args()

    cases = load_jsonl(CASES_FILE)
    if args.use_cached:
        outputs = {
            item["douban_id"]: item for item in load_jsonl(CACHE_FILE)
        }
    else:
        if not args.confirm_paid_run:
            raise SystemExit(
                "在线评测会调用付费接口，请加 --confirm-paid-run；"
                "或用 --use-cached 对历史输出免费判分。"
            )
        outputs = generate_live(cases, args.engine)
        if args.save_cache:
            with CACHE_FILE.open("w", encoding="utf-8") as file:
                for douban_id, record in outputs.items():
                    file.write(json.dumps(
                        {"douban_id": douban_id, **record}, ensure_ascii=False
                    ) + "\n")

    report = evaluate(cases, outputs)
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print_report(report)
    print(f"报告已写入 {REPORT_FILE}")


if __name__ == "__main__":
    main()
