# macOS ICNS 图标生成

## 一行命令生成 ICNS

```bash
python tools/build/generate_icns.py
```

## 输出位置

生成的 ICNS 文件将保存到：
```
build/generated/Owlangs.icns
```

## 工作流程

1. 从 Icon Composer 导出的 PNG 文件生成 ICNS
2. 源文件：`frontend/macos/Owlangs icon composer Exports/Owlangs icon composer-iOS-Default-1024x1024@1x.png`
3. 使用 Apple 的 `iconutil` 工具生成符合规范的 ICNS 文件
4. 自动处理所有必要的尺寸和缩放

## 打包使用

在运行 macOS 打包脚本之前，请先运行 ICNS 生成命令：

```bash
# 1. 生成 ICNS 图标
python tools/build/generate_icns.py

# 2. 运行打包脚本
bash tools/build/build_macos.sh lite
```

## 调试

如果生成的 ICNS 有问题，可以检查：

1. 源 PNG 文件是否存在
2. PNG 文件的透明度是否正确
3. `iconutil` 工具是否可用（macOS 自带）

## 自定义

如需使用其他风格的 PNG 文件，可以编辑 `tools/build/generate_icns.py` 中的源文件路径。

可用的 PNG 风格：
- `Owlangs icon composer-iOS-Default-1024x1024@1x.png` (默认)
- `Owlangs icon composer-iOS-Dark-1024x1024@1x.png`
- `Owlangs icon composer-iOS-ClearDark-1024x1024@1x.png`
- `Owlangs icon composer-iOS-ClearLight-1024x1024@1x.png`
- `Owlangs icon composer-iOS-TintedDark-1024x1024@1x.png`
- `Owlangs icon composer-iOS-TintedLight-1024x1024@1x.png`