"""Fictional presentation identities and group background for the demo."""
from datetime import timedelta

NAMES = {'279': '林老师', '201': '小禾妈妈', '198': '乐乐妈妈', '194': '朵朵爸爸', '176': '安安妈妈'}


def display_name(uid, default='家长'):
    return NAMES.get(str(uid), default)


def group_messages(anchor):
    """Stable fictional messages; never copied from imported customer conversations."""
    samples = [
        (279, 'teacher', '欢迎大家来到星芽阅读营！接下来我们一起陪孩子养成每天阅读的习惯。'),
        (201, 'parent', '大家好，我是小禾妈妈，孩子刚开始接触自主阅读。'),
        (198, 'parent', '我是乐乐妈妈，想了解每天安排多长时间比较合适。'),
        (279, 'teacher', '欢迎两位家长！可以先从孩子感兴趣的绘本开始，慢慢找到适合的节奏。'),
        (194, 'parent', '大家好，我是朵朵爸爸，孩子对动物故事特别感兴趣。'),
        (176, 'parent', '我是安安妈妈，孩子认字还不太多，能跟上阅读营吗？'),
        (279, 'teacher', '可以的，我们会根据孩子的情况一起看看适合的阅读方式，有问题随时聊。'),
        (201, 'parent', '小禾今天自己挑了一本故事书，听完还和我讲了最喜欢的角色。'),
        (279, 'teacher', '太棒了！愿意分享故事就是很好的开始，记得多鼓励孩子。'),
        (198, 'parent', '乐乐今天读了一会儿，但是有些字不认识，要不要马上提醒她？'),
        (279, 'teacher', '可以先让孩子结合图画猜一猜，再一起看看，不必急着纠正每个字。'),
        (194, 'parent', '朵朵今天选了恐龙绘本，读完还想再看一次。'),
        (176, 'parent', '安安这两天晚上不太愿意读，我有点担心。'),
        (279, 'teacher', '理解您的担心，我们可以先缩短阅读时间，选孩子喜欢的内容，慢慢来。'),
        (198, 'parent', '老师，后续阅读会员的价格和安排可以介绍一下吗？'),
    ]
    result = []
    for index, (uid, role, text) in enumerate(samples):
        at = anchor - timedelta(minutes=70 - index * 4)
        result.append({'id': f's:{index+1}', 'sender_id': str(uid), 'sender_name': display_name(uid),
                       'sender_role': role, 'type': 'text', 'text': text, 'time': at,
                       'original_time': at, 'source': '演示群聊'})
    return result
