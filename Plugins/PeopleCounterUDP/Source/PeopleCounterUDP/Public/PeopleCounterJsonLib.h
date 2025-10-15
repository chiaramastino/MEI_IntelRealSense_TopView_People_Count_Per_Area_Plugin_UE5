#pragma once
#include "Kismet/BlueprintFunctionLibrary.h"
#include "PeopleCounterJsonLib.generated.h"

UCLASS()
class PEOPLECOUNTERUDP_API UPeopleCounterJsonLib : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="PeopleCounter|JSON")
    static bool ParsePeopleCountPacket(const FString& JsonString,
        TMap<FString, int32>& OutSensors,
        double& OutTimestamp);
};
