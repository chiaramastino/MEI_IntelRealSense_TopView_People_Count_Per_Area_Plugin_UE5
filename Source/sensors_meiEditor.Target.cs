using UnrealBuildTool;
using System.Collections.Generic;

public class sensors_meiEditorTarget : TargetRules
{
    public sensors_meiEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("sensors_mei");
    }
}
