// Isolated module geometry/transition probe. Never install as a live event hook.
void Check(int ok, string name)
{
    WriteTimestampedLogEntry("RW_AREA_TEST " + name + (ok ? " PASS" : " FAIL"));
}

void Arrived(object actor, object target, string name)
{
    if (GetObjectType(target) == OBJECT_TYPE_DOOR)
        target = GetTransitionTarget(target);
    vector a = GetPosition(actor);
    vector t = GetPosition(target);
    WriteTimestampedLogEntry("RW_AREA_DETAIL " + name + " actor="
        + FloatToString(a.x) + "," + FloatToString(a.y) + "," + FloatToString(a.z)
        + " target=" + FloatToString(t.x) + "," + FloatToString(t.y) + "," + FloatToString(t.z)
        + " distance=" + FloatToString(GetDistanceBetween(actor, target))
        + " action=" + IntToString(GetCurrentAction(actor)));
    Check(GetIsObjectValid(actor) && GetArea(actor) == GetArea(target)
        && GetDistanceBetween(actor, target) < 2.0, name);
    DestroyObject(actor);
}

void Walk(string fromTag, string toTag, string name)
{
    object from = GetWaypointByTag(fromTag);
    object target = GetObjectByTag(toTag);
    object actor = CreateObject(OBJECT_TYPE_CREATURE, "rw_base", GetLocation(from));
    SetPlotFlag(actor, TRUE);
    AssignCommand(actor, ClearAllActions());
    AssignCommand(actor, ActionMoveToObject(target, TRUE, 1.0));
    DelayCommand(30.0, Arrived(actor, target, name));
}

void DoorLink(string tag, string targetTag, string areaTag)
{
    object door = GetObjectByTag(tag);
    object target = GetTransitionTarget(door);
    Check(GetIsObjectValid(door) && GetObjectType(door) == OBJECT_TYPE_DOOR
        && GetIsObjectValid(target) && GetTag(target) == targetTag
        && GetTag(GetArea(target)) == areaTag, tag + "_target");
    SetLocked(door, FALSE);
    AssignCommand(door, ActionOpenDoor(door));
}

void Probe()
{
    object chest = GetObjectByTag("rq_testchest");
    Check(GetIsObjectValid(chest) && GetObjectType(chest)==OBJECT_TYPE_PLACEABLE
        && GetHasInventory(chest) && GetUseableFlag(chest) && !GetLocked(chest)
        && !GetIsTrapped(chest) && GetDistanceBetween(chest,GetObjectByTag("rq_throne"))<5.0,
        "supplies_chest_by_throne");
    int sword=0,dagger=0,potions=0,bandages=0,total=0,usable=TRUE;
    object item=GetFirstItemInInventory(chest);
    while(GetIsObjectValid(item))
    {
        int count=GetItemStackSize(item);string ref=GetResRef(item);total+=count;
        if(ref=="nw_wswss001")sword+=count;
        else if(ref=="nw_wswdg001")dagger+=count;
        else if(ref=="nw_it_mpotion001")potions+=count;
        else if(ref=="nw_it_medkit001")bandages+=count;
        if(!GetIdentified(item) || !GetDroppableFlag(item) || GetPlotFlag(item))usable=FALSE;
        item=GetNextItemInInventory(chest);
    }
    Check(sword==1 && dagger==1 && potions==2 && bandages==1 && total==5 && usable,
        "supplies_chest_exact_usable_stock");
    Walk("rw_arr_hall_e", "rq_testchest", "supplies_chest_reachable");
    object forest = GetArea(GetWaypointByTag("rw_arr_forest"));
    object cave = GetArea(GetWaypointByTag("rw_arr_cave"));
    Check(GetIsObjectValid(forest) && !GetIsAreaInterior(forest)
        && GetIsAreaAboveGround(forest), "forest_outdoors");
    Check(GetIsObjectValid(cave) && GetIsAreaInterior(cave)
        && !GetIsAreaAboveGround(cave), "cave_underground");
    DoorLink("rw_hall_forest", "rw_arr_forest", "rw_forest");
    DoorLink("rw_hall_cave", "rw_arr_cave", "rw_cave");
    DoorLink("rw_forest_hall", "rw_arr_hall_w", "throne_room");
    DoorLink("rw_cave_hall", "rw_arr_hall_e", "throne_room");
    Walk("rw_arr_forest", "rw_rob_stage", "forest_path_walkable");
    Walk("rw_arr_cave", "rw_troll_hostage", "cave_path_walkable");
    Walk("rw_arr_hall_w", "rw_hall_forest", "hall_west_door_reachable");
    Walk("rw_arr_hall_e", "rw_hall_cave", "hall_east_door_reachable");
    Walk("rw_arr_forest", "rw_forest_hall", "forest_exit_reachable");
    Walk("rw_arr_cave", "rw_cave_hall", "cave_exit_reachable");
    DelayCommand(32.0, WriteTimestampedLogEntry("RW_AREA_TEST FINISHED"));
}

void main()
{
    DelayCommand(1.0, Probe());
}
