#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "UDPJsonSenderComponent.generated.h"

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class PEOPLECOUNTERUDP_API UUDPJsonSenderComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    FString TargetHost = TEXT("127.0.0.1");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    int32 TargetPort = 7780;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    bool bAutoConnect = true;

public:
    UUDPJsonSenderComponent();

    UFUNCTION(BlueprintCallable, Category="UDP")
    bool Connect();

    UFUNCTION(BlueprintCallable, Category="UDP")
    void Disconnect();

    UFUNCTION(BlueprintCallable, Category="UDP")
    bool IsConnected() const { return bConnected; }

    UFUNCTION(BlueprintCallable, Category="UDP")
    bool SendJsonString(const FString& JsonString);

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    class FSocket* SendSocket = nullptr;
    bool bConnected = false;

    bool CreateSocket();
    void DestroySocket();
};
