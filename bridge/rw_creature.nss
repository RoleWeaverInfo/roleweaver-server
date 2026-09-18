#include "nwnx_creature"
// Only newly created Role Weaver creatures are rebuilt. Existing world NPCs are never changed.
json RWField(json j, string k, json value)
{
    json field = JsonObjectGet(j,k);
    return JsonObjectSet(j,k,JsonObjectSet(field,"value",value));
}
int RWValidBuild(json b)
{
    int a=JsonGetInt(JsonObjectGet(b,"appearance"));
    int r=JsonGetInt(JsonObjectGet(b,"race"));
    int c=JsonGetInt(JsonObjectGet(b,"npc_class"));
    int g=JsonGetInt(JsonObjectGet(b,"gender"));
    int l=JsonGetInt(JsonObjectGet(b,"level"));
    return a>=0 && Get2DAString("appearance","LABEL",a)!="" && Get2DAString("appearance","LABEL",a)!="****"
        && r>=0 && r<=25 && r!=21 && r!=22 && c>=0 && c<=10 && g>=0 && g<=1 && l>=1 && l<=40;
}
object RWCreateCreature(json b, location loc)
{
    if (!RWValidBuild(b)) return OBJECT_INVALID;
    object seed=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",loc);
    if (!GetIsObjectValid(seed)) return OBJECT_INVALID;
    json j=ObjectToJson(seed); DestroyObject(seed);
    int c=JsonGetInt(JsonObjectGet(b,"npc_class"));
    int race=JsonGetInt(JsonObjectGet(b,"race"));
    int gender=JsonGetInt(JsonObjectGet(b,"gender"));
    int level=JsonGetInt(JsonObjectGet(b,"level"));
    json first=JsonArrayGet(JsonObjectGet(JsonObjectGet(j,"ClassList"),"value"),0);
    first=RWField(first,"Class",JsonInt(c)); first=RWField(first,"ClassLevel",JsonInt(1));
    j=RWField(j,"ClassList",JsonArrayInsert(JsonArray(),first));
    j=RWField(j,"FeatList",JsonArray());
    json skills=JsonObjectGet(JsonObjectGet(j,"SkillList"),"value");
    json emptySkills=JsonArray();int i;
    for(i=0;i<JsonGetLength(skills);i++) emptySkills=JsonArrayInsert(emptySkills,RWField(JsonArrayGet(skills,i),"Rank",JsonInt(0)));
    j=RWField(j,"SkillList",emptySkills);
    j=RWField(j,"Race",JsonInt(race));j=RWField(j,"Gender",JsonInt(gender));
    j=RWField(j,"Appearance_Type",JsonInt(JsonGetInt(JsonObjectGet(b,"appearance"))));
    j=RWField(j,"HitPoints",JsonInt(1));j=RWField(j,"CurrentHitPoints",JsonInt(1));j=RWField(j,"MaxHitPoints",JsonInt(1));
    j=RWField(j,"BaseAttackBonus",JsonInt(0));
    j=RWField(j,"StartingPackage",JsonInt(c));j=RWField(j,"xStartingPackage",JsonInt(c));
    j=RWField(j,"LawfulChaotic",JsonInt(50));j=RWField(j,"GoodEvil",JsonInt(50));
    if(c==5 || c==6) j=RWField(j,"LawfulChaotic",JsonInt(100));
    if(c==6) j=RWField(j,"GoodEvil",JsonInt(100));
    string abilities="StrDexConWisIntCha";
    for(i=0;i<6;i++)
    {
        string key=GetSubString(abilities,i*3,3);
        int score=StringToInt(Get2DAString("classes",key,c));
        if(score<10)score=10;
        if(race<=6)score+=StringToInt(Get2DAString("racialtypes",key+"Adjust",race));
        j=RWField(j,key,JsonInt(score));
    }
    object npc=JsonToObject(j,loc);
    if(!GetIsObjectValid(npc))return OBJECT_INVALID;
    NWNX_Creature_SetLevelByPosition(npc,0,0);
    NWNX_Creature_LevelUp(npc,c,level,c);
    if(GetHitDice(npc)!=level || GetClassByPosition(1,npc)!=c){DestroyObject(npc);return OBJECT_INVALID;}
    SetGender(npc,gender);
    SetLocalString(npc,"rw_creature",JsonDump(b));
    return npc;
}
