# Seagull 阅读数据协议

## 1. 项目概览

Seagull 负责采集 RSS/Atom 和 AI 自定义来源，并将内容转换为适合阅读端按需加载的静态 JSON。

项目包含两个分支：

- `main`：保存来源配置、采集和构建程序；
- `archive`：保存采集结果和阅读数据。

`archive` 中与阅读端有关的结构如下：

```text
archive
├── rendered.json
├── categories/
│   └── <node-id>/
│       ├── page-001.json
│       ├── page-002.json
│       └── ...
└── articles/
    └── <article-id>.json
```

阅读端不需要读取仓库目录，也不需要解析归档中的 RSS/Atom 文件。

## 2. 访问地址

### GitHub Pages

```text
Base URL:
https://0xzhangke.github.io/Seagull/data/

入口：
https://0xzhangke.github.io/Seagull/data/rendered.json
```

### Raw GitHub

同一份数据也可以从 `archive` 分支读取：

```text
Base URL:
https://raw.githubusercontent.com/0xZhangKe/Seagull/archive/

入口：
https://raw.githubusercontent.com/0xZhangKe/Seagull/archive/rendered.json
```

所有协议路径都是相对于 Base URL 的路径。

## 3. 读取流程

```text
GET rendered.json
       │
       ├── children[].pages[]
       │          │
       │          ▼
       │   GET categories/<node-id>/page-NNN.json
       │          │
       │          └── items[].detailPath
       │                     │
       │                     ▼
       │           GET articles/<article-id>.json
       │
       └── category.children[]
                   └── 子来源同样通过 pages 读取
```

基本顺序：

1. 请求 `rendered.json` 获取分类和来源；
2. 使用节点的 `pages` 数组请求文章列表；
3. 使用列表项的 `detailPath` 请求文章正文。

客户端应直接使用服务端返回的路径，不需要自行生成文件名或 ID。

## 4. `rendered.json`

`rendered.json` 是阅读数据的入口和导航索引：

```json
{
  "startedAt": "2026-09-24T00:20:07Z",
  "finishedAt": "2026-09-24T00:24:20Z",
  "durationSeconds": 253,
  "children": []
}
```

| 字段 | 类型 | 可空 | 含义 |
|---|---|---:|---|
| `startedAt` | string | 是 | 最近一轮采集的开始时间 |
| `finishedAt` | string | 是 | 最近一轮采集的结束时间 |
| `durationSeconds` | integer | 是 | 最近一轮采集耗时，单位为秒 |
| `children` | array | 否 | 顶层分类和来源 |

`children` 中当前有三种节点：

- `category`：分类；
- `rss`：RSS/Atom 来源；
- `ai`：AI 来源。

### 4.1 分类节点

```json
{
  "type": "category",
  "title": "Fedi",
  "articleCount": 270,
  "failed_count": 0,
  "pages": [
    "categories/folder-713179861d543485/page-001.json",
    "categories/folder-713179861d543485/page-002.json"
  ],
  "children": []
}
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `type` | string | 固定为 `category` |
| `title` | string | 分类名称 |
| `articleCount` | integer | 分类中的去重文章总数 |
| `failed_count` | integer | 最近一次采集失败的子来源数量 |
| `pages` | string[] | 分类聚合文章的分页路径 |
| `children` | object[] | 分类中的来源 |

分类的 `pages` 提供整个分类的聚合文章列表；`children` 提供分类中的各个来源。

### 4.2 来源节点

```json
{
  "type": "rss",
  "title": "Mastodon Engineering",
  "articleCount": 20,
  "state": 1.0,
  "pages": [
    "categories/2a7fab923fb5bdf4/page-001.json"
  ],
  "lastContentChangedAt": "2026-09-23T15:53:31Z",
  "lastSuccessfulFetchAt": "2026-09-24T00:20:08Z",
  "originalUrl": "https://mastodon.social/@MastodonEngineering.rss"
}
```

| 字段 | 类型 | 可空 | 含义 |
|---|---|---:|---|
| `type` | string | 否 | `rss` 或 `ai` |
| `title` | string | 否 | 来源名称 |
| `articleCount` | integer | 否 | 来源中的文章数 |
| `state` | number | 否 | 采集成功率，范围 `0.0` 到 `1.0` |
| `pages` | string[] | 否 | 来源文章的分页路径 |
| `lastContentChangedAt` | string | 是 | 来源内容最近一次变化时间 |
| `lastSuccessfulFetchAt` | string | 是 | 最近一次成功采集时间 |
| `originalUrl` | string | 是 | 原始 Feed URL；AI 来源通常为 `null` |

## 5. 分页文件

节点的 `pages` 数组包含完整分页路径，并按页码排列。每页最多 60 篇文章。

```json
{
  "items": [
    {
      "id": "70deb1e6aa6a3ccdce97f36a",
      "title": "文章标题",
      "summary": "纯文本摘要",
      "image": "https://example.com/image.png",
      "publishedAt": "2026-09-08T03:15:16Z",
      "sourceId": "02074271ad31198b",
      "sourceTitle": "最小可读",
      "link": "https://example.com/original",
      "detailPath": "articles/70deb1e6aa6a3ccdce97f36a.json"
    }
  ]
}
```

| 字段 | 类型 | 可空 | 含义 |
|---|---|---:|---|
| `items` | array | 否 | 当前页文章列表 |
| `id` | string | 否 | 稳定的文章 ID |
| `title` | string | 否 | 文章标题 |
| `summary` | string | 否 | 纯文本摘要 |
| `image` | string | 是 | 文章图片 URL |
| `publishedAt` | string | 是 | 发布时间 |
| `sourceId` | string | 否 | 来源 ID |
| `sourceTitle` | string | 否 | 来源名称 |
| `link` | string | 是 | 原文章 URL |
| `detailPath` | string | 否 | 文章详情路径 |

文章按时间从新到旧排列。分类分页会合并该分类中的来源，并按文章 ID 去重。

## 6. 文章详情

文章详情路径来自分页列表中的 `detailPath`：

```json
{
  "id": "70deb1e6aa6a3ccdce97f36a",
  "title": "文章标题",
  "summary": "纯文本摘要",
  "content": "<p>经过清理的 HTML 正文</p>",
  "image": null,
  "publishedAt": "2026-09-08T03:15:16Z",
  "sourceId": "02074271ad31198b",
  "sourceTitle": "最小可读",
  "link": "https://example.com/original"
}
```

文章详情包含分页条目的主要字段，并增加：

| 字段 | 类型 | 含义 |
|---|---|---|
| `content` | string | 构建阶段已经清理过的 HTML 正文 |

正文可能包含段落、标题、列表、引用、代码块、表格、图片和链接。正文中的链接和图片只保留有效的 HTTP(S) URL。

## 7. 数据约定

- JSON 和 HTML 字符串使用 UTF-8；
- 时间为 ISO 8601 UTC，例如 `2026-09-24T00:20:07Z`；
- `image`、`publishedAt`、`link`、来源时间和 `originalUrl` 可能为 `null`；
- `pages` 可能为空；
- 数组顺序就是展示或分页顺序；
- 文章 `id` 在来源和文章自身标识不变时保持稳定；
- `pages` 与 `detailPath` 均为相对路径；
- 协议未来可能增加字段，已有字段的类型和含义应保持兼容；
- 当前协议没有认证、写入或客户端状态同步接口。

## 8. 更新和一致性

归档采集完成后，阅读数据会重新构建并部署。构建时会同步删除已经失效的分页和文章文件。

静态文件之间没有事务型 HTTP 快照保证。在一次部署切换的短时间窗口内，可能出现：

- `rendered.json` 已更新，但新的分页文件暂时不可用；
- 调用方仍持有旧索引，而旧分页已经删除；
- 分页文件与文章详情文件短暂处于不同版本。

遇到这类情况时，相关文件可能返回 `404`。重新获取一次 `rendered.json` 可以判断索引是否已经变化；根节点的 `startedAt` 可作为采集轮次的比较值。

## 9. HTTP 行为

协议只需要 HTTP `GET`。

| 状态 | 含义 |
|---|---|
| `200` | 成功返回 JSON |
| `304` | 条件请求命中缓存 |
| `404` | 文件不存在、已经失效，或正处于部署切换窗口 |
| `429` | 静态服务实施限流 |
| `5xx` | GitHub Pages 或 Raw GitHub 临时异常 |

响应可能包含 `ETag`、`Last-Modified` 和 `Cache-Control`。这些响应头由 GitHub 静态服务提供，不属于 JSON 协议的固定字段。

## 10. 本地样例数据

在 Seagull 项目中运行：

```bash
python3 scripts/preview_pages.py --build-only
```

会在 `_mock_preview/data/` 生成完整样例：

```text
_mock_preview/data/rendered.json
_mock_preview/data/categories/.../page-001.json
_mock_preview/data/articles/<article-id>.json
```

这些文件与线上阅读数据使用相同协议。
