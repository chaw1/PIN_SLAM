# PIN-SLAM 使用手册补充

## 离职算法文档的补充说明

> 本文档基于原算法团队的调研文档，补充了故障排查、参数调优、数据质量要求等内容

---

## 📋 数据质量要求

### 输入数据必须满足的条件

1. **点云格式支持**：
   - .ply, .pcd, .bin, .las
   - 推荐使用 .ply (支持时间戳和颜色)

2. **点云质量要求**：
   - **每帧点数**：至少 500+ 点（密集场景推荐 5000+）
   - **帧率**：5-20 Hz（太低会tracking失败，太高无意义）
   - **时序连续性**：相邻帧重叠率 > 30%
   - **坐标系单位**：必须是米（不能是毫米）
   - **空间范围**：-100m ~ +100m 为宜

3. **必需的字段**：
   - positions (x, y, z) - 必需
   - timestamp / t / ts - 强烈推荐（用于去畸变）
   - intensity / colors - 可选（用于彩色建图）

4. **Ground Truth位姿（可选但推荐）**：
   - KITTI格式：12列的pose矩阵
   - TUM格式：timestamp x y z qx qy qz qw

### 数据加载器开发规范

参考已有的dataloader：
```bash
/home/jlw/PIN_SLAM/dataset/dataloaders/
├── four_d.py          # 行深多雷达
├── four_d_single.py   # 行深单雷达
├── caic.py            # 中汽数据
└── kitti.py           # 官方KITTI（参考模板）
```

**必须实现的方法**：
1. `__init__()` - 初始化数据路径
2. `__len__()` - 返回帧数
3. `__getitem__(idx)` - 返回第idx帧的点云
4. `get_gt_pose(idx)` - 返回GT位姿（如果有）

---

## 🔧 参数调优指南

### 已知的成功配置

| 场景类型 | 配置文件 | 关键参数 | 适用场景 |
|---------|---------|---------|---------|
| KITTI高清 | run_kitti_hd_annotation.yaml | mesh_min_nn=9 | 密集场景，高精度mesh |
| 行深彩色 | run_4d_color.yaml | 多雷达融合 | 城市道路，完整场景 |
| 中汽数据 | run_caic_color.yaml | 激进定位 | 定位困难场景 |
| 车道线 | run_lane.yaml | mesh_min_nn=5 | 稀疏线状特征 |

### 关键参数说明

#### 1. **neuralpoints.voxel_size_m** (神经点网格大小)
- **默认**: 0.4m
- **密集场景**: 0.2-0.3m （需要高精度）
- **稀疏场景**: 0.5-0.6m （节省内存）
- **影响**: 越小越精细，但内存占用越大

#### 2. **eval.mesh_min_nn** (Mesh重建最小近邻数)
- **默认**: 9
- **密集场景**: 10-15 （高质量mesh）
- **稀疏场景**: 3-5 （保证completeness）
- **影响**: 太大会导致稀疏区域无法重建

#### 3. **process.vox_down_m** (点云下采样)
- **默认**: 0.08m
- **高密度雷达**: 0.1-0.15m （加速处理）
- **低密度雷达**: 0.05-0.08m （保留细节）
- **影响**: 太大会丢失细节，太小会降低速度

#### 4. **tracker.iter_n** (Tracking迭代次数)
- **默认**: 100
- **困难场景**: 150-200 （中汽数据用的）
- **简单场景**: 50-80 （加速）
- **影响**: 迭代次数越多，定位越准确但越慢

#### 5. **decoder.freeze_after_frame** (解码器冻结帧数)
- **默认**: 40
- **稀疏场景**: 80-100 （充分学习）
- **密集场景**: 30-50 （快速收敛）
- **影响**: 冻结后只更新神经点，不更新decoder

---

## 🐛 常见失败模式及解决方案

### 失败模式1: Tracking漂移

**症状**：
- GUI中轨迹严重偏离ground truth
- 终端显示 registration error > 0.5
- 点云重影严重

**原因**：
- 场景重复特征多（如长直道路）
- 点云密度不足
- 相邻帧运动太大

**解决方案**：
```yaml
tracker:
  iter_n: 200              # 增加迭代次数
  source_vox_down_m: 0.3   # 降低tracking下采样
  GM_dist: 0.15            # 更严格的outlier阈值
```

### 失败模式2: Mesh为空或损坏

**症状**：
- mesh文件很小 (< 100KB)
- 打开mesh只有零星的碎片
- CloudCompare报错"无效PLY"

**原因**：
- **最常见**: mesh_min_nn太大，稀疏区域无法重建
- 神经点数量不足
- marching cubes分辨率不合适

**解决方案**：
```bash
# 方法1: 修改配置重新运行
# 在yaml中设置 mesh_min_nn: 5

# 方法2: 离线重建（如果neural_points.ply存在）
python vis_pin_map.py ./experiments/your_result \
    -c map/neural_points.ply \
    -m 0.05 \
    -n 3 \
    -o mesh_fixed.ply
```

### 失败模式3: GPU内存溢出

**症状**：
- CUDA out of memory
- 程序在某一帧crash
- GUI卡死

**原因**：
- batch_size太大
- pool_capacity太大
- 神经点数量爆炸

**解决方案**：
```yaml
continual:
  pool_capacity: 1e7       # 降低到1千万（默认2千万）
optimizer:
  batch_size: 8192         # 降低batch（默认16384）
eval:
  mesh_freq_frame: 200     # 降低mesh更新频率
```

或使用CPU模式（慢）：
```bash
python pin_slam.py config.yaml dataloader -c
```

### 失败模式4: 彩色建图失败

**症状**：
- mesh是灰色的
- 点云没有颜色
- 照片加载报错

**原因**：
- 照片路径不正确
- 照片和点云时间戳不匹配
- dataloader没有正确实现颜色加载

**检查清单**：
```python
# 在dataloader中检查：
1. 照片文件是否存在
2. 时间戳匹配逻辑是否正确
3. 是否调用了 self.config.color_on = True
4. 颜色值是否归一化到 [0, 1]
```

---

## 📈 性能基准

### 硬件配置
- CPU: 足够（tracking不太吃CPU）
- GPU: RTX 4090 24GB
- RAM: 32GB+

### 典型性能指标

| 数据集 | 帧数 | 处理时间 | FPS | 输出mesh大小 |
|-------|------|---------|-----|-------------|
| KITTI-00 | 4541 | ~2小时 | 0.6 | 50-100MB |
| 行深数据 | ~1000 | ~30分钟 | 0.5 | 80MB |
| 中汽数据 | ~800 | ~40分钟 | 0.3 | 60MB |

**注意**:
- 开启可视化会降低速度约20%
- mesh重建频率影响总时间
- PGO会在检测到loop时暂停

---

## 🔍 诊断工具使用

### check_ply.py - PLY文件诊断

**用途**: 检查生成的PLY文件是否有效

```bash
# 检查整个实验目录
python check_ply.py ./experiments/your_result_folder

# 检查单个文件
python check_ply.py ./experiments/your_result/map/neural_points.ply
```

**输出示例**：
```
============================================================
检查文件: neural_points.ply
============================================================
✓ 文件大小: 1245.67 KB
✓ Tensor版本读取成功

📊 点云属性:
  - positions: shape=(15234, 3), dtype=float64
  - intensities: shape=(15234, 1), dtype=float32

✓ 点数量: 15,234

📍 空间范围:
  X: [-120.456, 145.789]
  Y: [-85.123, 92.345]
  Z: [-5.678, 12.345]
```

**判断标准**：
- ✅ 点数量 > 10,000 且空间范围合理 → 成功
- ⚠️ 点数量 < 1,000 → 可能tracking失败
- ❌ 文件 < 100KB 或点数量 = 0 → 失败

---

## 📝 运行检查清单

每次运行PIN-SLAM前，检查以下项目：

### 数据准备
- [ ] 点云文件格式正确（.ply/.pcd/.bin）
- [ ] 文件命名符合dataloader要求（如00000.ply, 00001.ply...）
- [ ] 时间戳存在且连续
- [ ] 如有照片，路径和时间戳匹配

### 配置文件
- [ ] pc_path 指向正确的数据目录
- [ ] voxel_size_m 适合当前场景
- [ ] mesh_min_nn 不能太大（稀疏场景用3-5）
- [ ] o3d_vis_on: True （首次运行必须开启）

### 运行参数
- [ ] -d 参数（使用dataloader时必需）
- [ ] -v 参数（强烈推荐，可以实时监控）
- [ ] -s 参数（保存神经点）
- [ ] -m 或 -p （mesh或点云，至少选一个）

### 运行中监控
- [ ] Tracking error < 0.2 （在GUI或log中查看）
- [ ] Neural points数量持续增长
- [ ] 轨迹平滑连续（如有GT，应该接近）

### 结果验证
- [ ] 运行 `python check_ply.py experiments/结果文件夹`
- [ ] neural_points.ply 点数量 > 10,000
- [ ] mesh文件大小 > 1MB（如果生成了mesh）
- [ ] 在CloudCompare中打开查看质量

---

## 🆘 遇到问题时的标准流程

1. **检查日志**
   ```bash
   cat experiments/your_result/your_result.log
   ```

2. **运行诊断工具**
   ```bash
   python check_ply.py experiments/your_result
   ```

3. **检查关键指标**
   - Neural points数量
   - Registration error
   - Mesh vertices数量

4. **参考LANE_4D_GUIDE.md**
   - 详细的故障排查流程
   - 参数调优建议

5. **如果还是失败**
   - 提供: 配置文件、运行命令、完整log
   - 数据统计: 帧数、每帧点数、空间范围
   - check_ply.py的输出

---

## 📚 相关文档索引

- **原始调研文档** - 离职算法留下的技术路线和基础使用
- **LANE_4D_GUIDE.md** - 4D车道线专门指南
- **README.md** - PIN-SLAM官方文档
- **本文档** - 补充说明和故障排查

---

*最后更新: 2025-10-29*
*维护者: Claude Code*
