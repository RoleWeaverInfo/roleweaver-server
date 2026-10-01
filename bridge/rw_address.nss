// Conservative vocatives: Name:, Name, ... and Hello/Hi/Hey/Greetings[, ] Name.
string RWTrimAddress(string value)
{
    while (GetStringLeft(value, 1) == " ") value = GetSubString(value, 1, GetStringLength(value));
    while (GetStringLength(value) > 0 && FindSubString(" .!?", GetStringRight(value, 1)) >= 0)
        value = GetStringLeft(value, GetStringLength(value) - 1);
    return GetStringLowerCase(value);
}

string RWAddress(string text)
{
    text = RWTrimAddress(text);
    int greeting = FALSE;
    string first = GetStringLeft(text, FindSubString(text, " "));
    if (first == "hello" || first == "hello," || first == "hi" || first == "hi,"
        || first == "hey" || first == "hey," || first == "greetings" || first == "greetings,")
    {
        text = GetSubString(text, GetStringLength(first) + 1, GetStringLength(text));
        greeting = TRUE;
    }
    int split = FindSubString(text, ":");
    int comma = FindSubString(text, ",");
    if (comma >= 0 && (split < 0 || comma < split)) split = comma;
    if (split >= 0) return RWTrimAddress(GetStringLeft(text, split));
    if (greeting) return RWTrimAddress(text);
    return "";
}

// Short names omit one common title, so Captain Beran can be addressed as Beran.
string RWShortName(string name)
{
    name=RWTrimAddress(name);
    int split=FindSubString(name," ");
    if(split<0) return name;
    string first=GetStringLeft(name,split);
    if(FindSubString("|captain|sir|lady|lord|master|mistress|doctor|dr.|archmage|", "|"+first+"|")>=0)
    {
        name=RWTrimAddress(GetSubString(name,split+1,GetStringLength(name)));
        split=FindSubString(name," ");
        if(split<0) return name;
    }
    return GetStringLeft(name,split);
}
int RWNameMatch(string address,string exact,object npc,string alias="")
{
    string name=RWTrimAddress(GetName(npc));
    string id=GetLocalString(npc,"rw_id");
    if ((address!="" && (address==name || (id!="" && address==id)))
        || exact==name || (id!="" && exact==id)) return 1;
    string shortName=RWShortName(name);
    if(shortName!="" && (address==shortName || exact==shortName)) return 1;
    alias=RWTrimAddress(alias);
    if(alias!="" && (address==alias || exact==alias))return 1;
    return 0;
}
