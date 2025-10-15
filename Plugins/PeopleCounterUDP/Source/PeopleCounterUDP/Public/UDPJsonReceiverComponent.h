#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"

// 🔧 TIPI DEL RECEIVER/ENDPOINT
#include "Common/UdpSocketReceiver.h" // FArrayReaderPtr, FUdpSocketReceiver
#include "Interfaces/IPv4/IPv4Endpoint.h"             // FIPv4Endpoint

#include "UDPJsonReceiverComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnJsonReceived, const FString&, JsonString);

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class PEOPLECOUNTERUDP_API UUDPJsonReceiverComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    FString ListenAddress = TEXT("0.0.0.0");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    int32 ListenPort = 7777;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    bool bAutoStart = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="UDP")
    bool bLogPackets = false;

    UPROPERTY(BlueprintAssignable, Category="UDP")
    FOnJsonReceived OnJsonReceived;

public:
    UUDPJsonReceiverComponent();

    UFUNCTION(BlueprintCallable, Category="UDP")
    bool StartReceiver();

    UFUNCTION(BlueprintCallable, Category="UDP")
    void StopReceiver();

    UFUNCTION(BlueprintCallable, Category="UDP")
    bool IsRunning() const { return bRunning; }

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    // Socket + thread del receiver
    FUdpSocketReceiver* SocketReceiver = nullptr;
    FSocket*            ListenSocket   = nullptr;
    bool                bRunning       = false;

    // Callback esatta per FUdpSocketReceiver
    void HandlePacket(const FArrayReaderPtr& Data, const FIPv4Endpoint& Endpoint);

    bool CreateSocket();
    void DestroySocket();
};
