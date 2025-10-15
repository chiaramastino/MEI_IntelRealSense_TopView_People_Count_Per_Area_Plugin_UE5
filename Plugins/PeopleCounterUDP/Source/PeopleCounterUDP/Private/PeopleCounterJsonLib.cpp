#include "PeopleCounterJsonLib.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

bool UPeopleCounterJsonLib::ParsePeopleCountPacket(const FString& JsonString,
    TMap<FString, int32>& OutSensors,
    double& OutTimestamp)
{
    OutSensors.Empty();
    OutTimestamp = 0.0;

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        return false;
    }

    FString Schema, Type;
    Root->TryGetStringField(TEXT("schema"), Schema);
    Root->TryGetStringField(TEXT("type"), Type);
    Root->TryGetNumberField(TEXT("timestamp"), OutTimestamp);

    const TArray<TSharedPtr<FJsonValue>>* SensorsArray = nullptr;
    if (Root->TryGetArrayField(TEXT("sensors"), SensorsArray))
    {
        for (const TSharedPtr<FJsonValue>& V : *SensorsArray)
        {
            if (!V.IsValid() || V->Type != EJson::Object) continue;
            TSharedPtr<FJsonObject> Obj = V->AsObject();
            if (!Obj.IsValid()) continue;

            FString Id;
            int32 Count = 0;
            Obj->TryGetStringField(TEXT("id"), Id);
            Obj->TryGetNumberField(TEXT("count"), Count);
            if (!Id.IsEmpty())
            {
                OutSensors.Add(Id, Count);
            }
        }
    }
    return true;
}
