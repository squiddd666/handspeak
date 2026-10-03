"""Requested vocabulary and explicit source mappings; no invented training availability."""
import json,re
from pathlib import Path
ROOT=Path('/opt/handspeak/repository');WORK=Path('/opt/handspeak-training/vocabulary-v7')
GROUPS={
'Greetings & Communication':"Good morning, Good afternoon, Good evening, Welcome, Excuse me, You're welcome, Understand, Don't understand, Again, Repeat, Slow, Name, Sign, Speak, Listen",
'Daily Needs':'Hungry, Thirsty, Full, Hot, Cold, Clothes, Shoes, Money, Phone, Charger, Bed, Shower, Rest, Work',
'Health & Emergency':'Pain, Sick, Fever, Headache, Stomachache, Accident, Ambulance, Nurse, Pharmacy, Blood, Injury, Dizzy, Breathe, Allergy',
'Family & People':'Brother, Sister, Grandmother, Grandfather, Baby, Child, Boy, Girl, Man, Woman, Parent, Classmate',
'School':'School, Classroom, Book, Paper, Pen, Pencil, Computer, Assignment, Homework, Exam, Question, Answer, Read, Write, Study, Learn',
'Actions':'Walk, Run, Give, Take, Bring, Buy, Pay, Look, See, Watch, Hear, Call, Send, Find, Know, Remember, Forget',
'Places':'Home, School, Hospital, Store, Restaurant, Church, Office, Police station, Pharmacy, Market, Road, Room',
'Transportation':'Car, Bus, Motorcycle, Bicycle, Taxi, Train, Airplane, Ride, Drive',
'Time':'Today, Tomorrow, Yesterday, Now, Later, Morning, Afternoon, Evening, Night, Early, Late, Hour, Minute',
'Numbers':'Zero, One, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten, Eleven, Twelve, Thirteen, Fourteen, Fifteen, Sixteen, Seventeen, Eighteen, Nineteen, Twenty, Hundred, Thousand',
'Feelings':'Excited, Worried, Nervous, Confused, Surprised, Bored, Lonely, Fine, Okay, Love, Like, Dislike',
'Safety':"Careful, Don't touch, Stay, Leave, Lost, Safe, Unsafe, Call police, Call ambulance",
'Common objects':'Door, Window, Table, Chair, Bag, Key, Wallet, Bottle, Glass, Plate, Spoon, Umbrella',
'Food':'Rice, Bread, Chicken, Fish, Meat, Vegetable, Fruit, Milk, Coffee, Breakfast, Lunch, Dinner',
'Question/response words':"Which, How many, How much, Can, Cannot, Want, Don't want, Need, Have, Don't have, Maybe, Because"
}
def slug(s):return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
# Only close lexical mappings; do not substitute another word for a phrase.
ALIASES={'Grandmother':'grandma','Grandfather':'grandpa','Shoes':'shoe','Speak':'talk','Call':'callonphone','Pain':'owie','Full':'fullfood','Need':'needneedto'}
NOTES={'Call':'Example is CALL ON PHONE, not calling out to someone.','Pain':'Example is the general PAIN/HURT concept; location-specific signs may differ.','Full':'FULL in the food/eating sense.'}
versions={v:set(json.loads((Path(__file__).resolve().parent/'source-labels'/(v+'.json')).read_text())) for v in ['v1_0','v2_1']}
items={};categories=[]
for group,words in GROUPS.items():
 gid=slug(group);categories.append({'id':gid,'name':group})
 for label in words.split(', '):
  key=slug(label)
  if key in items:items[key]['categories'].append(gid);continue
  source=ALIASES.get(label,label.lower().replace(' ',''));version=next((v for v in versions if source in versions[v]),None)
  items[key]={'id':key,'label':label.upper(),'categories':[gid],'sourceLabel':source if version else None,'sourceVersion':version,'recognition':'not-pretrained','note':NOTES.get(label,''),'video':None,'learningUrl':f'https://signdata.cc.gatech.edu/view/datasets/popsign_{version}/game/{source}/index.html' if version else None}
for label in ['Hungry','Book','Like']:
 items[slug(label)].update(recognition='existing-preview',video='media/signs/'+slug(label)+'.mp4')
catalog={'version':1,'language':'ASL','categories':categories,'items':list(items.values())}
(ROOT/'models/motion-vocabulary.json').write_text(json.dumps(catalog,indent=2)+'\n');WORK.mkdir(exist_ok=True);(WORK/'requested-catalog.json').write_text(json.dumps(catalog,indent=2))
print('Unique words:',len(items),'Category memberships:',sum(len(i['categories']) for i in items.values()))
print('v1 sources:',sum(i['sourceVersion']=='v1_0' for i in items.values()),'v2 only:',sum(i['sourceVersion']=='v2_1' for i in items.values()),'Unmatched:',sum(not i['sourceVersion'] for i in items.values()))
