# ThreeJSON 可视化边界

[中文](threejson-visualization-boundary.md) | [English](../en/threejson-visualization-boundary.md)

## 目的

ThreeMind 使用 ThreeJSON 作为意识图像的 UI 侧场景运行时基础。此次接入提升的是
渲染吞吐与运行时对象管理；它不会把任何意识规则、模型包规则或持久化规则搬进
浏览器。

渲染器只是观察者。它不能创建、增强、削弱、删除或解释 Core 中的节点与连接。

## 边界

```text
ThreeMind Core
  -> OutputBus / WebSocket 图快照与增量
  -> UI GraphProjectionStore
  -> 建立在 ThreeJSON Runtime 上的 ThreeMindGraph 可视化域
  -> Three.js GPU 场景与画布
```

Core 只发布 ThreeMind 领域数据：节点、连接、激活、稳定度、触达标识、空间坐标、
删除事件与生命周期指标。UI 投影存储负责合并这些消息；可视化域再把已合并的
视图映射到 GPU 资源。

Core 不反向依赖 ThreeJSON。Core 代码不导入 ThreeJSON，`.tmind` 模型包也不含
ThreeJSON ID、几何对象、着色器状态或浏览器专用元数据。

## 运行时投影

UI 有两个刻意分离的表示：

- **GraphProjectionStore**：按节点和连接 ID 建索引的、仅属于 UI 的可变投影。
  它先应用完整快照，再合并增量。
- **ThreeMindGraph 域**：专门的呈现域，只拥有
  `threemind:node:42`、`threemind:edge:42:75` 这类可视化句柄。它们是 ThreeJSON
  运行时实体 ID，不是 Core 节点语义，也不属于持久化模型数据。

WebSocket 变化会立即更新投影存储。React 仅以动画帧频率接收合帧后的快照，用于
计数器和面板；图形域则直接接收精确增量。这样不会因为每一次激活事件都通过
React 重建整个图。

## GPU 更新模型

图形域使用 ThreeJSON 的动态点批次和线段批次。节点变化只更新自身的点槽位与
相邻线段槽位；删除实体只释放自己的槽位。帧提交调度器会合并这些脏区间，并在
下一帧上传到 GPU。

这与每个 Core 事件后都完整重建场景或完整上传顶点缓冲区不同。高频激活和连接
变化保持在局部可视化投影中。

可选的显示漂移仍只是呈现功能，不会改变 Core 的坐标、拓扑、记忆、联想、遗忘
或任何已记录的实验状态。它默认关闭。

## 渲染器与回退

新的 UI 设置默认使用 `threejson` 作为 3D 渲染器，同时保留明确的选择：

- **ThreeJSON GPU 投影**：默认的增量渲染模式。
- **Three.js 旧版回退**：保留此前的渲染器，便于对照或恢复。
- **Canvas 2D**：经典二维回退模式。

已保存的旧式 `three` 设置不会被静默改写，仍会继续使用旧版渲染器，直到用户
自行选择其他模式。

## 版本范围

首轮接入基于 `threejson@0.1.0-alpha.9`、`@threejson/assets@1.1.3` 与
`three@0.184.x`。ThreeMind 只使用 ThreeJSON 的公开导出与自身的可视化域，不导入
私有包路径。

未来可选的 ThreeJSON 优化，是新增一个窄的公开运行时入口，只导出场景运行时、
动态批次、提交调度器与运行时实体注册表。它可以缩小按需加载的图形渲染代码块，
但并非本次接入正确运行的前提。
