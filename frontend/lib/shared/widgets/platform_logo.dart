import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

/// AI平台Logo组件
/// 支持显示真实logo图片或fallback图标
class PlatformLogo extends StatelessWidget {
  const PlatformLogo({
    required this.platformKey,
    super.key,
    this.size = 24.0,
    this.fallbackColor,
    this.fit = BoxFit.contain,
  });
  final String platformKey;
  final double size;
  final Color? fallbackColor;
  final BoxFit fit;

  @override
  Widget build(BuildContext context) {
    final String? logoPath = _getLogoPath(platformKey);

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * 0.1),
        color: Colors.white,
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 2,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(size * 0.1),
        child:
            logoPath != null ? _buildLogoImage(logoPath) : _buildFallbackIcon(),
      ),
    );
  }

  /// 构建logo图片
  Widget _buildLogoImage(String logoPath) {
    if (logoPath.endsWith('.svg')) {
      return SvgPicture.asset(
        logoPath,
        width: size,
        height: size,
        fit: fit,
        placeholderBuilder: (BuildContext context) => _buildFallbackIcon(),
      );
    } else {
      return Image.asset(
        logoPath,
        width: size,
        height: size,
        fit: fit,
        errorBuilder:
            (BuildContext context, Object error, StackTrace? stackTrace) =>
                _buildFallbackIcon(),
      );
    }
  }

  /// 获取平台logo路径
  String? _getLogoPath(String platformKey) {
    switch (platformKey) {
      case 'openai':
        return 'images/logos/openai.svg';
      case 'anthropic':
        return 'images/logos/anthropic.svg';
      case 'google':
        return 'images/logos/google.svg';
      case 'azure':
        return 'images/logos/azure.svg';
      case 'deepseek':
        return 'images/logos/deepseek.svg';
      case 'zhipu':
        return 'images/logos/zhipu.svg';
      case 'moonshot':
        return 'images/logos/moonshot.svg';
      case 'volcengine_ark':
        return 'images/logos/volcengine.svg';
      case 'aleph_alpha':
        return 'images/logos/aleph_alpha.svg';
      case 'rinna':
        return 'images/logos/rinna.svg';
      case 'naver':
        return 'images/logos/naver.svg';
      case 'groq':
        return 'images/logos/groq.svg';
      case 'cohere':
        return 'images/logos/cohere.svg';
      case 'xai':
        return 'images/logos/xai.svg';
      case 'mistral':
        return 'images/logos/mistral.svg';
      case 'custom':
        return 'images/logos/custom.svg';
      default:
        return null;
    }
  }

  /// 构建fallback图标
  Widget _buildFallbackIcon() {
    final IconData icon = _getFallbackIcon(platformKey);
    final Color color = fallbackColor ?? _getPlatformColor(platformKey);

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(size * 0.1),
      ),
      child: Icon(
        icon,
        size: size * 0.6,
        color: color,
      ),
    );
  }

  /// 获取fallback图标
  IconData _getFallbackIcon(String platformKey) {
    switch (platformKey) {
      case 'openai':
        return Icons.smart_toy;
      case 'anthropic':
        return Icons.psychology;
      case 'google':
        return Icons.search;
      case 'azure':
        return Icons.cloud;
      case 'deepseek':
        return Icons.auto_awesome;
      case 'zhipu':
        return Icons.psychology;
      case 'moonshot':
        return Icons.nightlight_round;
      case 'volcengine_ark':
        return Icons.rocket_launch;
      case 'aleph_alpha':
        return Icons.auto_awesome;
      case 'rinna':
        return Icons.flag;
      case 'naver':
        return Icons.language;
      case 'groq':
        return Icons.speed;
      case 'cohere':
        return Icons.merge;
      case 'xai':
        return Icons.close;
      case 'mistral':
        return Icons.wind_power;
      case 'custom':
        return Icons.settings;
      default:
        return Icons.help_outline;
    }
  }

  /// 获取平台颜色
  Color _getPlatformColor(String platformKey) {
    switch (platformKey) {
      case 'openai':
        return Colors.green;
      case 'anthropic':
        return Colors.orange;
      case 'google':
        return Colors.blue;
      case 'azure':
        return Colors.blue.shade800;
      case 'deepseek':
        return Colors.purple;
      case 'zhipu':
        return Colors.red;
      case 'moonshot':
        return Colors.indigo;
      case 'volcengine_ark':
        return Colors.amber;
      case 'aleph_alpha':
        return Colors.teal;
      case 'rinna':
        return Colors.pink;
      case 'naver':
        return Colors.green.shade700;
      case 'groq':
        return Colors.cyan;
      case 'cohere':
        return Colors.deepOrange;
      case 'xai':
        return Colors.black;
      case 'mistral':
        return Colors.blueGrey;
      case 'custom':
        return Colors.grey;
      default:
        return Colors.grey.shade600;
    }
  }
}

/// 平台Logo列表组件
/// 用于显示多个平台的logo
class PlatformLogoList extends StatelessWidget {
  const PlatformLogoList({
    required this.platformKeys,
    super.key,
    this.size = 24.0,
    this.spacing = 8.0,
    this.maxDisplay = 5,
    this.onMorePressed,
  });
  final List<String> platformKeys;
  final double size;
  final double spacing;
  final int maxDisplay;
  final VoidCallback? onMorePressed;

  @override
  Widget build(BuildContext context) {
    final List<String> displayKeys = platformKeys.take(maxDisplay).toList();
    final int remainingCount = platformKeys.length - maxDisplay;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        ...displayKeys.map(
          (String key) => Padding(
            padding: EdgeInsets.only(right: spacing),
            child: PlatformLogo(
              platformKey: key,
              size: size,
            ),
          ),
        ),
        if (remainingCount > 0)
          GestureDetector(
            onTap: onMorePressed,
            child: Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                color: Colors.grey.shade200,
                borderRadius: BorderRadius.circular(size * 0.1),
                border: Border.all(color: Colors.grey.shade300),
              ),
              child: Center(
                child: Text(
                  '+$remainingCount',
                  style: TextStyle(
                    fontSize: size * 0.4,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey.shade600,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
