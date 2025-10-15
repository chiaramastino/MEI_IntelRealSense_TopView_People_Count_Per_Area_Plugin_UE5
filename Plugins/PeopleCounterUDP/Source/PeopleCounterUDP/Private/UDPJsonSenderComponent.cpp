#include "UDPJsonSenderComponent.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "IPAddress.h"
#include "Common/UdpSocketBuilder.h"

DEFINE_LOG_CATEGORY_STATIC(LogPeopleCounterUDP_TX, Log, All);

UUDPJsonSenderComponent::UUDPJsonSenderComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UUDPJsonSenderComponent::BeginPlay()
{
    Super::BeginPlay();
    if (bAutoConnect)
    {
        Connect();
    }
}

void UUDPJsonSenderComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Disconnect();
    Super::EndPlay(EndPlayReason);
}

bool UUDPJsonSenderComponent::CreateSocket()
{
    if (SendSocket) return true;

    bool bIsValid = false;
    TSharedRef<FInternetAddr> Addr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
    Addr->SetIp(*TargetHost, bIsValid);
    if (!bIsValid)
    {
        UE_LOG(LogPeopleCounterUDP_TX, Error, TEXT("Invalid TargetHost: %s"), *TargetHost);
        return false;
    }
    Addr->SetPort(TargetPort);

    SendSocket = FUdpSocketBuilder(TEXT("PeopleCounterUDP_TX"))
        .AsNonBlocking()
        .AsReusable()
        .WithSendBufferSize(2 * 1024 * 1024);

    if (!SendSocket)
    {
        UE_LOG(LogPeopleCounterUDP_TX, Error, TEXT("Failed to create UDP send socket."));
        return false;
    }
    bConnected = true;
    return true;
}

void UUDPJsonSenderComponent::DestroySocket()
{
    if (SendSocket)
    {
        SendSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(SendSocket);
        SendSocket = nullptr;
    }
    bConnected = false;
}

bool UUDPJsonSenderComponent::Connect()
{
    return CreateSocket();
}

void UUDPJsonSenderComponent::Disconnect()
{
    DestroySocket();
    UE_LOG(LogPeopleCounterUDP_TX, Log, TEXT("UDP Sender disconnected"));
}

bool UUDPJsonSenderComponent::SendJsonString(const FString& JsonString)
{
    if (!SendSocket)
    {
        if (!CreateSocket()) return false;
    }

    bool bIsValid = false;
    TSharedRef<FInternetAddr> Addr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
    Addr->SetIp(*TargetHost, bIsValid);
    if (!bIsValid)
    {
        UE_LOG(LogPeopleCounterUDP_TX, Error, TEXT("Invalid TargetHost: %s"), *TargetHost);
        return false;
    }
    Addr->SetPort(TargetPort);

    FTCHARToUTF8 Conv(*JsonString);
    int32 BytesSent = 0;
    bool bOK = SendSocket->SendTo((uint8*)Conv.Get(), Conv.Length(), BytesSent, *Addr);

    if (!bOK)
    {
        UE_LOG(LogPeopleCounterUDP_TX, Warning, TEXT("SendTo failed to %s:%d"), *TargetHost, TargetPort);
    }
    return bOK;
}
