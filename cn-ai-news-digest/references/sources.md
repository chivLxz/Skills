# RSS 数据源配置

## 数据源状态（v1.0.0）

全部使用直接 RSS feed，无第三方依赖。

| 媒体 | 优先级 | RSS 地址 | 状态 |
|------|--------|----------|------|
| 量子位 | P0 | `https://www.qbitai.com/feed` | ✅ 稳定 |
| 36氪 | P0 | `https://36kr.com/feed` | ✅ 稳定 |
| 机器之心 | P0 | `https://www.jiqizhixin.com/rss` | ⚠️ XML 偶有格式异常，已做容错处理 |
| InfoQ 中文 | P0 | `https://www.infoq.cn/feed` | ✅ 稳定 |
| 爱范儿 | P1 | `https://www.ifanr.com/feed` | ✅ 稳定 |
| 钛媒体 | P1 | `https://www.tmtpost.com/rss` | ✅ 稳定 |
| 雷锋网 | P1 | `https://www.leiphone.com/feed` | ✅ 稳定 |

## 容错机制

- 机器之心 RSS 偶尔出现 XML 格式错误（mismatched tag），脚本会自动降级为正则提取
- 日期过滤不足时自动扩展至近 3 天

## 数据来源说明

RSS 地址参考自 [tech-news-digest](https://github.com/draco-agent/tech-news-digest) 的中文源配置。
