WSE Federal Enforcement 5.0 的 iOS 兼容修复测试版，保留新增人物和车辆模型。

修复内容：
- 使用与 5.0 人物模型匹配的性格定义，在原版装备表上追加 WSE 预设；缺失的现代武器替换为本体现有枪械。
- 修正巡逻艇布局、操控定义及部分新增车辆的音效引用。
- 按明确游戏路径打包，避免自动安装误选 `backup` 旧配置。
- 保留 Classic 5.0 警察出警阵容；去掉引用缺失 DLC 人车的非警察 BIKER/ASSASSINS 紧急事件。

安装：先在游戏“设置 > Mods”中停用或删除旧 WSE，再导入 `GTA5_WSE_Federal_iOS_Compat_v1.0.zip`，完全重启游戏。原有小弟修改器继续保留；本包不覆盖 `script_wasm.rpf` 或 `weapons.meta`。

已通过 8 项静态依赖/资源检查，并在干净目录重建出逐字节一致的安装包。尚未 iPhone 实测，请依次测试 1 星、3 星、5 星；若仍停机，保留新日志用于继续定位。

附件：
- `GTA5_WSE_Federal_iOS_Compat_v1.0.zip`：安装包，约 154 MiB。
- `GTA5_WSE_Federal_iOS_Compat_v1.0_Source.zip`：构建源码与诊断记录，约 807 KiB；重建需另备原作者 5.0 ZIP。
- `SHA256SUMS.txt`：下载完整性校验。

原模组作者：DonKrushko 及原包列明的资源贡献者。原版与授权说明：[WSE Federal Enforcement](https://www.gta5-mods.com/misc/wanted-system-enhancement-federal-enforcement)。本包为兼容修改版，不代表原作者或移植项目官方版本。
