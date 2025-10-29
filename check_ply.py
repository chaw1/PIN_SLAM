#!/usr/bin/env python3
"""
PLY文件诊断工具
用于检查PIN-SLAM生成的PLY文件是否有效
"""

import os
import sys
import open3d as o3d
import numpy as np

def check_ply_file(ply_path):
    """检查PLY文件的完整性和内容"""
    print(f"\n{'='*60}")
    print(f"检查文件: {ply_path}")
    print(f"{'='*60}")

    # 1. 检查文件是否存在
    if not os.path.exists(ply_path):
        print("❌ 错误: 文件不存在!")
        return False

    # 2. 检查文件大小
    file_size = os.path.getsize(ply_path)
    print(f"✓ 文件大小: {file_size / 1024:.2f} KB")

    if file_size < 100:  # 小于100字节基本是空文件
        print("❌ 警告: 文件太小，可能是空文件或损坏!")
        return False

    # 3. 尝试读取PLY文件
    try:
        # 尝试tensor版本读取
        print("\n尝试用 o3d.t.io 读取...")
        pcd_t = o3d.t.io.read_point_cloud(ply_path)
        print("✓ Tensor版本读取成功")

        # 检查点云属性
        print("\n📊 点云属性:")
        for key, value in pcd_t.point.items():
            shape = value.shape
            dtype = value.dtype
            print(f"  - {key}: shape={shape}, dtype={dtype}")

        # 转换为numpy查看统计信息
        if "positions" in pcd_t.point:
            positions = pcd_t.point["positions"].numpy()
            num_points = len(positions)
            print(f"\n✓ 点数量: {num_points:,}")

            if num_points == 0:
                print("❌ 错误: 点云为空!")
                return False

            print(f"\n📍 空间范围:")
            print(f"  X: [{positions[:, 0].min():.3f}, {positions[:, 0].max():.3f}]")
            print(f"  Y: [{positions[:, 1].min():.3f}, {positions[:, 1].max():.3f}]")
            print(f"  Z: [{positions[:, 2].min():.3f}, {positions[:, 2].max():.3f}]")

            # 检查是否有异常值
            if np.any(np.isnan(positions)) or np.any(np.isinf(positions)):
                print("❌ 警告: 检测到NaN或Inf值!")
                return False

        return True

    except Exception as e:
        print(f"❌ Tensor版本读取失败: {e}")

        # 尝试legacy版本读取
        try:
            print("\n尝试用 o3d.io 读取...")
            pcd = o3d.io.read_point_cloud(ply_path)
            print("✓ Legacy版本读取成功")

            num_points = len(pcd.points)
            print(f"✓ 点数量: {num_points:,}")

            if num_points == 0:
                print("❌ 错误: 点云为空!")
                return False

            points = np.asarray(pcd.points)
            print(f"\n📍 空间范围:")
            print(f"  X: [{points[:, 0].min():.3f}, {points[:, 0].max():.3f}]")
            print(f"  Y: [{points[:, 1].min():.3f}, {points[:, 1].max():.3f}]")
            print(f"  Z: [{points[:, 2].min():.3f}, {points[:, 2].max():.3f}]")

            if pcd.has_colors():
                print("✓ 包含颜色信息")
            if pcd.has_normals():
                print("✓ 包含法线信息")

            return True

        except Exception as e2:
            print(f"❌ Legacy版本读取也失败: {e2}")
            return False

def check_mesh_file(ply_path):
    """检查mesh PLY文件"""
    print(f"\n{'='*60}")
    print(f"检查Mesh文件: {ply_path}")
    print(f"{'='*60}")

    if not os.path.exists(ply_path):
        print("❌ 错误: 文件不存在!")
        return False

    file_size = os.path.getsize(ply_path)
    print(f"✓ 文件大小: {file_size / 1024:.2f} KB")

    try:
        mesh = o3d.io.read_triangle_mesh(ply_path)

        num_vertices = len(mesh.vertices)
        num_triangles = len(mesh.triangles)

        print(f"✓ 顶点数量: {num_vertices:,}")
        print(f"✓ 三角形数量: {num_triangles:,}")

        if num_vertices == 0 or num_triangles == 0:
            print("❌ 错误: Mesh为空!")
            return False

        vertices = np.asarray(mesh.vertices)
        print(f"\n📍 空间范围:")
        print(f"  X: [{vertices[:, 0].min():.3f}, {vertices[:, 0].max():.3f}]")
        print(f"  Y: [{vertices[:, 1].min():.3f}, {vertices[:, 1].max():.3f}]")
        print(f"  Z: [{vertices[:, 2].min():.3f}, {vertices[:, 2].max():.3f}]")

        if mesh.has_vertex_colors():
            print("✓ 包含顶点颜色")
        if mesh.has_vertex_normals():
            print("✓ 包含顶点法线")

        # 检查mesh质量
        if not mesh.is_edge_manifold():
            print("⚠️  警告: Mesh不是边流形(edge manifold)")
        if not mesh.is_vertex_manifold():
            print("⚠️  警告: Mesh不是顶点流形(vertex manifold)")

        return True

    except Exception as e:
        print(f"❌ 读取mesh失败: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python check_ply.py <ply文件路径>")
        print("或者: python check_ply.py <实验目录>  (自动检查所有PLY文件)")
        sys.exit(1)

    path = sys.argv[1]

    if os.path.isdir(path):
        # 扫描目录中的所有PLY文件
        print(f"\n扫描目录: {path}")
        ply_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.ply'):
                    ply_files.append(os.path.join(root, file))

        if not ply_files:
            print("❌ 未找到PLY文件!")
            sys.exit(1)

        print(f"找到 {len(ply_files)} 个PLY文件\n")

        results = {}
        for ply_file in sorted(ply_files):
            if 'mesh' in ply_file.lower():
                results[ply_file] = check_mesh_file(ply_file)
            else:
                results[ply_file] = check_ply_file(ply_file)

        # 总结
        print(f"\n{'='*60}")
        print("检查总结:")
        print(f"{'='*60}")
        for ply_file, success in results.items():
            status = "✓" if success else "❌"
            print(f"{status} {os.path.basename(ply_file)}")

    else:
        # 检查单个文件
        if 'mesh' in path.lower():
            check_mesh_file(path)
        else:
            check_ply_file(path)

if __name__ == "__main__":
    main()
