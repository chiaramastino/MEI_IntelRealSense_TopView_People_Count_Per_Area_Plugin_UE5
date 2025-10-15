using UnrealBuildTool;
using System.Collections.Generic;

public class sensors_meiTarget : TargetRules
{
    public sensors_meiTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("sensors_mei");
    }
}
