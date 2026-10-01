// Demo captive relationship repair: no decaying reputation modifiers.
void RQCaptiveRelation(object captive, object other, int friendly)
{
 if(!GetIsObjectValid(captive) || !GetIsObjectValid(other) || captive==other)return;
 ClearPersonalReputation(other,captive);
 ClearPersonalReputation(captive,other);
 if(friendly)
 {
  SetIsTemporaryFriend(other,captive,FALSE);
  SetIsTemporaryFriend(captive,other,FALSE);
 }
 // Other cast members use the demo faction table's neutral baseline.
}
