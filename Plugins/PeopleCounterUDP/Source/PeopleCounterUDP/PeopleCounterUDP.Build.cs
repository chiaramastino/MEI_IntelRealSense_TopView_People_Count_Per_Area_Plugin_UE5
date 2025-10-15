using UnrealBuildTool;

public class PeopleCounterUDP : ModuleRules
{
    public PeopleCounterUDP(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine",
            "Sockets", "Networking", "Json", "JsonUtilities"
        });

        PrivateDependencyModuleNames.AddRange(new string[] { });
    }
}
