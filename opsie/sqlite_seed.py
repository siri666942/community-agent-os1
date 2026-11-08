"""Build the redistributable SQLite seed using only invented demo data."""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .demo_data import NAMES

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / 'data' / 'opsie-demo.sqlite3'

SCHEMA = '''
CREATE TABLE users(user_id INTEGER PRIMARY KEY,display_name TEXT,profile TEXT);
CREATE TABLE opsie_accounts(account_id INTEGER PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT NOT NULL,role TEXT NOT NULL,user_id INTEGER UNIQUE,display_name TEXT,active INTEGER DEFAULT 1);
CREATE TABLE opsie_sessions(token_hash TEXT PRIMARY KEY,account_id INTEGER NOT NULL,expires_at TEXT NOT NULL);
CREATE TABLE conversations(conversation_id INTEGER PRIMARY KEY,conversation_type TEXT,title TEXT,created_by_user_id INTEGER,settings TEXT,conversation_status TEXT DEFAULT 'active',last_message_at TEXT);
CREATE TABLE conversation_members(conversation_id INTEGER,user_id INTEGER,member_role TEXT,member_status TEXT DEFAULT 'active',PRIMARY KEY(conversation_id,user_id));
CREATE TABLE direct_conversation_pairs(conversation_id INTEGER,user_low_id INTEGER,user_high_id INTEGER,PRIMARY KEY(user_low_id,user_high_id));
CREATE TABLE messages(message_id INTEGER PRIMARY KEY AUTOINCREMENT,conversation_id INTEGER NOT NULL,sender_user_id INTEGER,client_message_id TEXT,source_system TEXT,external_message_id TEXT,message_type TEXT DEFAULT 'text',body TEXT,created_at TEXT,message_status TEXT DEFAULT 'active',reply_to_message_id INTEGER,UNIQUE(sender_user_id,client_message_id),UNIQUE(source_system,external_message_id));
CREATE INDEX message_by_conversation ON messages(conversation_id,created_at,message_id);
CREATE TABLE opsie_demo(demo_key TEXT PRIMARY KEY,group_id INTEGER,source_group_id INTEGER,offset_seconds INTEGER,created_at TEXT);
CREATE TABLE opsie_inbound_reviews(message_key TEXT PRIMARY KEY,conversation_id INTEGER,sender_id INTEGER,effective_time TEXT,status TEXT,is_sensitive INTEGER,details TEXT,policy_version TEXT,updated_at TEXT);
CREATE TABLE opsie_jobs(job_id TEXT PRIMARY KEY,account_id INTEGER,conversation_id INTEGER,target_message_key TEXT,target_user_id INTEGER,context_revision TEXT,policy_version TEXT,status TEXT,result TEXT,error TEXT,created_at TEXT,updated_at TEXT);
CREATE INDEX job_by_conversation ON opsie_jobs(conversation_id,created_at);
CREATE TABLE opsie_outbound_reviews(review_id INTEGER PRIMARY KEY AUTOINCREMENT,conversation_id INTEGER,account_id INTEGER,text_hash TEXT,status TEXT,details TEXT,confirmed INTEGER DEFAULT 0,variant TEXT,edited INTEGER,message_id INTEGER,policy_version TEXT,created_at TEXT);
CREATE TABLE opsie_tags(tag_id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,tag TEXT,account_id INTEGER,created_at TEXT,UNIQUE(user_id,tag));
CREATE TABLE opsie_profile_cache(user_id INTEGER PRIMARY KEY,summary TEXT,source_revision TEXT,updated_at TEXT);
CREATE TABLE opsie_library_entries(entry_id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,title TEXT,content TEXT,level TEXT,updated_by INTEGER,updated_at TEXT);
CREATE TABLE opsie_library_meta(meta_key TEXT PRIMARY KEY,created_at TEXT);
'''

DAYS = ['第一天','第二天','第三天','第四天','第五天','第六天','第七天','第八天','第九天','第十天','第十一天','第十二天','第十三天','第十四天','第十五天','第十六天','第十七天','第十八天','第十九天','第二十天','第二十一天']
PARENTS = [201, 198, 194, 176]
PEER_NAMES = ['小禾', '乐乐', '朵朵', '安安']
PRIVATE_QUESTIONS = [
    ['小禾最近总让我陪着读，怎么让她慢慢自己看？','绘本里不认识的字需要一个个教吗？','她喜欢动物故事，有推荐的入门方式吗？','昨天看了几页就跑去玩了，是不是坐不住？','今天她自己选了一本小熊的故事。','讲故事的时候我需要一直提问吗？','如果晚上太晚了，第二天补读可以吗？','后面的阅读会员怎么安排？'],
    ['乐乐喜欢听故事，但还不愿意自己读，该怎么办？','她读到不认识的字会有点着急。','今天她看图猜出了故事结尾，特别开心。','需要每天规定必须读完一本吗？','她总是想反复读同一本绘本。','可以让她读给爷爷奶奶听吗？','周末出门没带平板，阅读节奏会受影响吗？','能帮我了解一下会员价格吗？'],
    ['朵朵对恐龙很感兴趣，可以从这类绘本开始吗？','他认识一些字，但是读得比较慢。','今天他给我讲了故事里的霸王龙。','遇到长句子要不要帮他念完？','他想边看图边编自己的故事。','孩子读完之后，家长怎么鼓励比较好？','我们通常周末才有时间陪读。','后续有哪些资料可以先看看？'],
    ['安安识字不多，也能参加阅读营吗？','她有时候读几分钟就不想继续了。','今天她挑了一本关于小兔子的绘本。','孩子读错的时候，我担心纠正会打击她。','这两天她愿意自己点开绘本了。','我可以每天换个时间陪她读吗？','如果孩子一直不喜欢阅读，应该怎么引导？','报名后如果有疑问，可以找谁核实？'],
]
PRIVATE_REPLIES = [
    ['可以先陪她挑选喜欢的内容，再慢慢留一点自己看的时间。','不必逐字打断，可以结合图画理解，不熟悉的字一起看看。','动物故事很适合作为兴趣入口，可以让小禾自己挑一本。','短时间阅读也可以，先让过程轻松，比时长更重要。','真棒，愿意自己挑选就是很好的开始。','不用一直提问，读完聊聊她最喜欢的角色就好。','可以按家庭节奏灵活安排，不必为了补读给孩子压力。','好的，具体安排我先帮您核实清楚。'],
    ['可以先亲子共读，让乐乐熟悉之后再试着自己看几页。','先鼓励她结合图片猜一猜，觉得困难时我们再一起看。','能联系图画猜结尾很棒，可以请她讲讲为什么这么想。','不用强求读完，先找到她舒服的阅读节奏。','反复读喜欢的故事很正常，也有助于熟悉内容。','当然可以，分享故事也是很好的表达练习。','不用担心一次缺席，回来后继续轻松阅读就好。','可以，我先核实当前适用的价格和相关信息。'],
    ['可以，先从朵朵感兴趣的恐龙故事入手很合适。','阅读速度可以慢慢来，不需要追求一次读得很快。','太好了！愿意主动分享，说明他对故事有自己的理解。','可以先给他一点时间，需要帮助时再一起读。','很棒，可以让他自由表达，再看看原故事怎样发展。','具体夸奖他的观察或表达，会比只说“真棒”更有帮助。','可以先从周末亲子共读开始，再看平日是否方便。','好的，我帮您整理并核实可以提供的资料。'],
    ['可以先了解安安喜欢的故事，再一起选择适合的阅读内容。','先从短一点的时间开始，让她觉得阅读是愉快的。','小兔子故事听起来很适合她，可以让她讲讲喜欢的情节。','可以先肯定她的尝试，再自然地一起看看那个字。','进步很棒，记得鼓励她自己选择喜欢的绘本。','可以，按你们的日常安排找到舒服的时间就好。','先了解她不喜欢的原因，从她感兴趣的话题慢慢尝试。','有问题可以先告诉我，我帮您核实后再回复。'],
]
GROUP_QUESTIONS = [
    ['大家好，我是小禾妈妈，很高兴和大家一起陪孩子阅读！','今天小禾选了一本森林故事，回来一直在讲小熊。','想请教一下，孩子老问故事里的问题，大家会怎么回答？','小禾昨天只读了几分钟，我准备今天让她自己选书。','她今天居然记住了故事里小狐狸的名字。','孩子喜欢听大人读，自己开口还比较少。','我们家准备把睡前十分钟留给绘本。','谢谢老师，这周感觉亲子阅读轻松多了。'],
    ['大家好，我是乐乐妈妈，第一次带孩子参加阅读营。','乐乐今天对海洋动物的绘本特别感兴趣。','孩子读错字的时候，大家会直接纠正吗？','今天她让我把一个故事讲了两遍。','乐乐把喜欢的角色画了下来，特别认真。','孩子有时候只看图不读字，这样也可以吗？','周末准备和乐乐去图书馆逛逛。','老师，后续阅读会员的价格可以帮我核实吗？'],
    ['我是朵朵爸爸，孩子很喜欢恐龙，希望能认识更多绘本。','朵朵今天看完一本恐龙故事，还问了好多问题。','我们家晚上比较忙，早餐后读一会儿可以吗？','他今天自己编了一个小恐龙的结局。','朵朵和奶奶分享了他最喜欢的那一页。','孩子念得比较慢，应该给他更多时间吗？','今天他主动提醒我要一起看故事了。','感谢大家分享，我们准备继续保持这个习惯。'],
    ['大家好，我是安安妈妈，孩子刚开始接触自主阅读。','安安今天选了小兔子的故事，让我陪她一起看。','孩子还不认识太多字，看绘本会不会太难？','今天她看着图片讲出了一个自己的故事。','安安读完说也想养一只小兔子。','这两天她不太想读，我打算换一本试试。','今天只读了一小会儿，但她心情很好。','谢谢老师的建议，我会多听听她喜欢什么。'],
]
GROUP_REPLIES = [
    ['欢迎小禾妈妈！很开心和大家一起开启阅读之旅。','小禾愿意分享喜欢的角色，值得好好鼓励。','可以先听听她自己的想法，再一起探索答案。','让她自己选感兴趣的故事，是个不错的尝试。','记住角色说明她在认真观察，可以让她再讲讲。','可以先由大人陪读，等她愿意时再邀请她分享。','睡前共读是很温暖的安排，按舒服的节奏就好。','听到您的反馈很开心，继续享受亲子阅读吧。'],
    ['欢迎乐乐妈妈，有任何阅读问题都可以交流。','海洋故事很有趣，可以让乐乐选喜欢的动物聊聊。','可以先肯定她的尝试，再自然地一起看看。','反复听喜欢的故事很正常，也能增加熟悉感。','画出故事角色是很好的表达方式！','可以，先通过图画理解故事也是阅读的一部分。','图书馆有很多选择，让乐乐自己挑选也很好。','好的，具体价格和适用安排我先帮您核实。'],
    ['欢迎朵朵爸爸，喜欢恐龙就是很好的阅读入口。','愿意提出问题很棒，可以陪他一起找找答案。','可以，适合家庭的时间就是好时间。','自己编结局很有创意，鼓励他继续分享。','能和家人分享喜欢的内容，非常棒。','可以多给他一些时间，不用急着追求速度。','主动提出一起阅读是很好的变化！','感谢分享，找到适合自己的节奏最重要。'],
    ['欢迎安安妈妈，刚开始可以先从喜欢的图画故事入手。','陪伴她一起选择和阅读，是很好的开始。','不用担心，可以先结合图画理解内容。','能用自己的话讲故事，很值得鼓励！','她已经开始联系故事和自己的想法了，很棒。','可以试试换个主题，先照顾孩子的阅读兴趣。','轻松愉快的体验很重要，短时间也可以。','不客气，有新情况随时和我交流。'],
]
LIBRARY = [
    ('standard','产品与权益','具体产品权益待确认，请先核实。',None),
    ('standard','价格与优惠','价格和活动待确认，请先核实当前适用口径。',None),
    ('standard','退费规则','先理解家长诉求，具体退费规则需核实，不承诺随时退或一律不能退。',None),
    ('standard','测评与试听','是否免费及预约方式待确认，请先核实。',None),
    ('risk','绝对效果承诺','不得保证每个孩子必然达到某个阅读效果或识字数量。','red'),
    ('risk','退款承诺','不得擅自承诺随时退或无条件退款。','red'),
    ('risk','群聊隐私','不得在群里披露孩子或家庭的个人隐私。','red'),
    ('risk','未经核实的价格与优惠','不得承诺未经核实的价格、锁价或优惠。','yellow'),
    ('risk','夸大师资或效果','师资和效果描述需要事实依据，不确定时先核实。','yellow'),
]


def build(path=SEED):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'种子库已存在，未覆盖：{path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        anchor = datetime(2025, 1, 15, 18, 0, 0)
        people = [(279, 'teacher', 'teacher')] + [(uid, f'parent{i+1}', 'parent') for i, uid in enumerate(PARENTS)]
        for index, (uid, username, role) in enumerate(people):
            daily = {day: {'是否阅读': '是' if (n+index) % (index+2) else '否',
                           '阅读时长': f'{8+(n+index)%9}分{(n*7)%60}秒' if (n+index) % (index+2) else 0}
                     for n, day in enumerate(DAYS)} if role == 'parent' else {}
            profile = {'daily_reading': daily, 'tested': '已测字', 'signup': '已报名', 'baby_age': 5 + index % 3} if daily else {}
            db.execute('INSERT INTO users VALUES(?,?,?)', (uid, NAMES[str(uid)], json.dumps(profile, ensure_ascii=False)))
            db.execute('INSERT INTO opsie_accounts(account_id,username,password_hash,role,user_id,display_name) VALUES(?,?,?,?,?,?)',
                       (index+1, username, '', role, uid, NAMES[str(uid)]))
        settings = json.dumps({'opsie_demo': 'reading-camp-v1'})
        db.execute('INSERT INTO conversations(conversation_id,conversation_type,title,created_by_user_id,settings) VALUES(4,?,?,279,?)', ('group','星芽阅读营交流群',settings))
        for uid, _, role in people:
            db.execute('INSERT INTO conversation_members(conversation_id,user_id,member_role) VALUES(4,?,?)', (uid, 'owner' if role == 'teacher' else 'member'))
        db.execute('INSERT INTO opsie_demo VALUES(?,?,?,?,?)', ('reading-camp-v1',4,0,0,anchor.isoformat(' ')))
        seq = 0
        def message(cid, uid, text, when):
            nonlocal seq
            seq += 1
            db.execute('INSERT INTO messages(conversation_id,sender_user_id,source_system,external_message_id,message_type,body,created_at) VALUES(?,?,?,?,?,?,?)',
                       (cid, uid, 'opsie_demo_seed', f'fiction-{seq}', 'text', text, when.isoformat(' ')))
        for i, uid in enumerate(PARENTS):
            cid = 5+i
            db.execute('INSERT INTO conversations(conversation_id,conversation_type,created_by_user_id,settings) VALUES(?,\'direct\',279,?)', (cid,settings))
            for member in (279, uid): db.execute('INSERT INTO conversation_members(conversation_id,user_id,member_role) VALUES(?,?,?)', (cid,member,'owner' if member==279 else 'member'))
            db.execute('INSERT INTO direct_conversation_pairs VALUES(?,?,?)', (cid,min(uid,279),max(uid,279)))
            for n, (question, reply) in enumerate(zip(PRIVATE_QUESTIONS[i], PRIVATE_REPLIES[i])):
                at = anchor - timedelta(hours=48-n*4,minutes=i*3)
                message(cid, uid, question.replace('孩子',PEER_NAMES[i]), at)
                message(cid, 279, reply.replace('孩子',PEER_NAMES[i]), at+timedelta(minutes=5))
        for n in range(8):
            for i, uid in enumerate(PARENTS):
                at = anchor - timedelta(hours=24) + timedelta(minutes=(n*4+i)*35)
                message(4, uid, GROUP_QUESTIONS[i][n], at)
                message(4, 279, GROUP_REPLIES[i][n], at+timedelta(minutes=3))
        db.execute('UPDATE conversations SET last_message_at=(SELECT MAX(created_at) FROM messages WHERE messages.conversation_id=conversations.conversation_id)')
        db.executemany('INSERT INTO opsie_library_entries(kind,title,content,level,updated_by,updated_at) VALUES(?,?,?,?,1,?)', [(*row,anchor.isoformat(' ')) for row in LIBRARY])
        db.execute('INSERT INTO opsie_library_meta VALUES(?,?)', ('initial_library',anchor.isoformat(' ')))
        db.commit()
    finally:
        db.close()
    print(f'已生成纯虚构种子库：{path} ({path.stat().st_size} bytes)')


if __name__ == '__main__':
    build()
