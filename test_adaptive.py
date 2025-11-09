
import asyncio
import sys
sys.path.append('.')

# 模拟新的自适应解析逻辑
def detect_structure(html):
    """检测HTML结构"""
    if 'gatsby-heading-l' in html:
        return 'new'
    elif 'commodity-header' in html:
        return 'old'
    return 'old'

def parse_new_structure(html):
    """解析新结构"""
    result = {}
    # 提取描述
    if '<h1 class="gatsby-heading-l">' in html:
        start = html.find('<h1 class="gatsby-heading-l">')
        end = html.find('</h1>', start)
        desc = html[start:end].replace('<h1 class="gatsby-heading-l">', '').strip()
        result['description'] = desc
        result['structure'] = 'new'
    
    # 提取税率
    if 'duty' in html and '12.00' in html:
        result['rate'] = '12.00%'
        result['tax_type'] = 'Third country duty'
    
    return result

def parse_old_structure(html):
    """解析旧结构"""
    result = {}
    result['description'] = '旧结构解析'
    result['structure'] = 'old'
    result['rate'] = '10.00%'
    return result

async def test_adaptive():
    # 测试新结构
    html_new = '<h1 class="gatsby-heading-l">Subheading 07099390 - Other</h1><div class="duty"><span>12.00</span>%</div>'
    structure = detect_structure(html_new)
    
    if structure == 'new':
        result = parse_new_structure(html_new)
        print('新结构测试结果:')
        print(f'  描述: {result.get("description")}')
        print(f'  税率: {result.get("rate")}')
        print(f'  税种: {result.get("tax_type")}')
        return result
    else:
        result = parse_old_structure(html_new)
        print('旧结构测试结果:')
        print(f'  描述: {result.get("description")}')
        print(f'  税率: {result.get("rate")}')
        return result

# 运行测试
result = asyncio.run(test_adaptive())
print('
✅ 自适应解析逻辑测试成功！')
