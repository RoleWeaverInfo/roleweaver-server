// Isolated runner substitutes only player/association lookup with fixture locals.
// Buffering, privacy filters, distance, visibility and lifecycle rules are real.
#include "rw_hearing"
void Check(int ok,string label)
{WriteTimestampedLogEntry("RW_HEARING_TEST "+(ok?"PASS ":"FAIL ")+label);}
void main()
{
    object m=GetModule(),area=GetFirstArea();
    SetLocalString(m,"rw_session","hearing-test");SetLocalString(m,"rw_cpp_generation","test");
    SetLocalInt(m,"rw_cp_enabled",TRUE);SetLocalInt(m,"rw_cp_listening",TRUE);SetLocalInt(m,"rw_tick",200);
    location at=Location(area,Vector(15.0,15.0,0.0),0.0);
    object owner=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",at);
    object familiar=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",at);
    object speaker=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",at);
    SetLocalInt(owner,"fixture_pc",TRUE);SetLocalObject(m,"fixture_owner",owner);
    SetLocalObject(owner,"fixture_familiar",familiar);SetLocalObject(familiar,"fixture_master",owner);
    // Native default initialization must preserve an explicit off choice, even
    // through resummoning, menu refreshes and a server policy toggle.
    RWCPInitialize(owner);
    Check(GetLocalInt(owner,"rw_cp_on") && GetLocalString(owner,"rw_cp_login_session")=="hearing-test","companion AI defaults on for a new player login");
    RWCPSetEnabled(owner,FALSE);RWCPInitialize(owner);
    Check(!GetLocalInt(owner,"rw_cp_on"),"repeated initialization preserves player off");
    SetLocalObject(owner,"fixture_familiar",OBJECT_INVALID);RWCPInitialize(owner);
    SetLocalObject(owner,"fixture_familiar",familiar);RWCPInitialize(owner);
    Check(!GetLocalInt(owner,"rw_cp_on"),"resummoning does not override player off");
    SetLocalInt(m,"rw_cp_enabled",FALSE);RWCPInitialize(owner);
    SetLocalInt(m,"rw_cp_enabled",TRUE);RWCPInitialize(owner);
    Check(!GetLocalInt(owner,"rw_cp_on"),"server switch does not override player off");
    DeleteLocalInt(m,RWCPLoginKey(owner));RWCPInitialize(owner);
    Check(GetLocalInt(owner,"rw_cp_on"),"new login restores enabled default despite stale character locals");
    RWCPInitialize(speaker);
    Check(!GetLocalInt(speaker,"rw_cp_on"),"nonplayer cannot acquire default AI controls");
    SetLocalInt(speaker,"fixture_pc",TRUE);SetLocalInt(speaker,"fixture_dm",TRUE);RWCPInitialize(speaker);
    Check(!GetLocalInt(speaker,"rw_cp_on"),"DM excluded from player default");
    SetLocalInt(speaker,"fixture_dm",FALSE);SetLocalInt(speaker,"fixture_possessed",TRUE);RWCPInitialize(speaker);
    Check(!GetLocalInt(speaker,"rw_cp_on"),"possessed character excluded from player default");
    SetLocalInt(speaker,"fixture_possessed",FALSE);SetLocalInt(m,"rw_cp_enabled",FALSE);RWCPInitialize(speaker);
    Check(!GetLocalInt(speaker,"rw_cp_on") && !RWCPReady(owner,familiar),"server disable blocks default and active AI");
    SetLocalInt(m,"rw_cp_enabled",TRUE);RWCPInitialize(speaker);
    Check(GetLocalInt(speaker,"rw_cp_on"),"default starts when service later enables companions");
    SetLocalInt(speaker,"fixture_pc",FALSE);
    SetLocalInt(owner,"rw_cpp_loaded",TRUE);SetLocalString(owner,"rw_cpp_identity",RWCPSettingsIdentity(owner));
    SetLocalString(owner,"rw_cpp_session","hearing-test");SetLocalString(owner,"rw_cpp_generation","test");
    json prefs=RWCPDefaultPrefs();
    Check(!RWI(prefs,"listening"),"listening defaults off");
    prefs=JsonObjectSet(prefs,"listening",JsonInt(1));SetLocalString(owner,"rw_cpp_value",JsonDump(prefs));
    SetName(speaker,"Grust");SetCreatureAppearanceType(speaker,APPEARANCE_TYPE_TROLL);
    SetDescription(speaker,"A towering troll clutching a crude club.");
    Check(FindSubString(GetStringLowerCase(RWVisibleAppearance(speaker)),"troll")>=0,"visible troll appearance");
    json surroundings=RWSurroundings(familiar);int found=FALSE,i;
    for(i=0;i<JsonGetLength(surroundings);i++)
    {json row=JsonArrayGet(surroundings,i);if(RWS(row,"label")=="Grust" && FindSubString(RWS(row,"description"),"crude club")>=0)found=TRUE;}
    Check(found,"public creature description in visual snapshot");
    Check(RWCPHearEnabled(owner,familiar),"enabled owned familiar can listen");
    Check(RWCPHearAudible(familiar,speaker),"visible nearby speech audible");
    Check(!RWCPHearAudible(familiar,familiar),"own speech excluded");
    object far=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(area,Vector(80.0,80.0,0.0),0.0));
    Check(!RWCPHearAudible(familiar,far),"out of range speech excluded");
    Check(!RWCPHearPublicText(speaker,"private",NWNX_CHAT_CHANNEL_PLAYER_TELL),"tell excluded");
    Check(!RWCPHearPublicText(speaker,"private",NWNX_CHAT_CHANNEL_PLAYER_PARTY),"party excluded");
    Check(!RWCPHearPublicText(speaker,"private",NWNX_CHAT_CHANNEL_PLAYER_WHISPER),"whisper excluded");
    Check(!RWCPHearPublicText(speaker,"private",NWNX_CHAT_CHANNEL_PLAYER_TALK,owner),"targeted talk excluded");
    Check(!RWCPHearPublicText(speaker," \t/rw companion settings",1),"helper command excluded");
    Check(!RWCPHearPublicText(speaker," ((out of character))",1),"OOC excluded");
    RWCPHearPublic(speaker,"Pay for her freedom.");
    Check(JsonGetLength(RWCPHearRecent(familiar))==1,"public demand enters history once");
    Check(RWPublicSpeak("Please help me!",speaker),"normal public broadcast succeeds");
    Check(JsonGetLength(RWCPHearRecent(familiar))==2,"Role Weaver broadcast captured once");
    SetLocalInt(speaker,"fixture_pc",TRUE);SetName(speaker,"Private player name");
    RWCPHearPublic(speaker,"We can help.");
    json lines=RWCPHearRecent(familiar);json last=JsonArrayGet(lines,JsonGetLength(lines)-1);
    Check(RWS(last,"speaker")=="Unidentified traveler" && RWS(last,"speaker_kind")=="player","player nameplate omitted");
    SetLocalInt(speaker,"fixture_pc",FALSE);
    for(i=0;i<12;i++){SetLocalInt(m,"rw_tick",201+i);RWCPHearPublic(speaker,"Line "+IntToString(i));}
    Check(JsonGetLength(RWCPHearRecent(familiar))==8,"history bounded to eight lines");
    SetLocalInt(m,"rw_tick",333);Check(JsonGetLength(RWCPHearRecent(familiar))==0,"old lines expire");
    RWCPHearPublic(speaker,"New line");SetLocalObject(familiar,"rw_heard_area",OBJECT_INVALID);
    Check(JsonGetLength(RWCPHearRecent(familiar))==0,"area change clears history");
    RWCPHearPublic(speaker,"Another line");SetLocalString(m,"rw_cpp_generation","changed");
    Check(JsonGetLength(RWCPHearRecent(familiar))==0,"service generation clears history");SetLocalString(m,"rw_cpp_generation","test");
    RWCPHearPublic(speaker,"Last line");SetLocalString(owner,"rw_cpp_value",JsonDump(JsonObjectSet(prefs,"listening",JsonInt(0))));
    Check(JsonGetLength(RWCPHearRecent(familiar))==0,"turning listening off clears history");
    Check(GetLocalString(familiar,"rw_heard")=="","disabled buffer is discarded");
    WriteTimestampedLogEntry("RW_HEARING_TEST FINISHED");
}
