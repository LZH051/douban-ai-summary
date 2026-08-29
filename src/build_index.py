"""构建语义索引（命令行入口）。

- 配置了 AI_EMBEDDING_MODEL 时走付费 embedding 接口，需要
  --confirm-paid-run 显式确认；
- 未配置时可用 --offline-hash 构建零费用的字面匹配索引（无语义，
  仅供本地演示与测试）。
- 幂等：按 douban_id upsert，内容未变的电影跳过，不重复计费。
"""

import argparse
import logging

from embeddings import ApiEmbedder, HashingEmbedder, api_embedder_configured
from logging_setup import configure_logging
from semantic_index import build_index

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="构建电影语义索引")
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument(
        "--offline-hash", action="store_true",
        help="使用零费用的哈希 embedding（无语义，仅演示/测试）",
    )
    args = parser.parse_args()

    if args.offline_hash:
        embedder = HashingEmbedder()
    else:
        if not api_embedder_configured():
            raise SystemExit(
                "未配置 AI_EMBEDDING_MODEL/AI_API_KEY/AI_BASE_URL。"
                "本地演示可加 --offline-hash 构建零费用索引。"
            )
        if not args.confirm_paid_run:
            raise SystemExit("embedding 调用可能产生费用，请添加 --confirm-paid-run。")
        embedder = ApiEmbedder()

    report = build_index(embedder)
    logger.info(
        "索引构建完成：共 %d 部电影，本次向量化 %d，未变化跳过 %d（embedder=%s）",
        report["total_movies"], report["embedded"],
        report["skipped_unchanged"], report["embedder"],
    )


if __name__ == "__main__":
    main()
