# Run-2 反馈改进 — GCP dev 自测截图（2026-07-02 凌晨）

所有图均在 **GCP dev** 上用真实输出文件跑 render worker 生成（非 MSU）。

## A. 图例可读性（Run-2 反馈 #1：Cori/Nick "legend too small / no title/units"）
改动：通用 InVEST 图例放大到 **2x + bold**，栅格/graduated 放进右侧白 gutter 不压图，栅格加文件名标题 + 高置信单位。

| 图 | 展示 |
|----|------|
| `jpg_raster.jpg` | 连续栅格色带：标题 **"Wyield (mm)"** 粗体、2x 色带、数字不裁、不压图 |
| `jpg_graduated.jpg` | graduated 矢量：字段名 `precip_mn` header + 色带（该 shp 单要素→三个数字相同，是数据非 bug） |
| `jpg_categorical.jpg` | categorical：合成 4 类，swatch + gutter（服务器无现成 LISA/cluster 输出，故合成验此分支） |
| `jpg_telecoupling.jpg` | telecoupling flow 回归：样式未被图例改动破坏 |

## B. telecoupling 点 marker 放大（Run-2 A1：Xin 37/38/39 "markers small/faint at wide extent"）
改动：systems 三角 7.5→11、agents 人形 9→13、causes 星 7.5→11 + 加粗描边。

| BEFORE | AFTER | 展示 |
|--------|-------|------|
| `jpg_systems.jpg` | `jpg_systems2.jpg` | systems 绿三角明显放大、更醒目 |
| `jpg_agents.jpg` | `jpg_agents2.jpg` | agents 人形放大、白描边提对比 |
| — | `jpg_causes2.jpg` | causes 红星 + **categorical "Causes" 图例**（A2 在 GCP 本就已是 categorical，非连续色带） |

> 对比看 systemsX / agentsX 两组即可感受放大效果。
