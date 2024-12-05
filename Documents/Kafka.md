```mermaid
graph TB
    subgraph Producers
        P1[Producer 1]
        P2[Producer 2]
        P3[Producer 3]
    end

    subgraph "Kafka Cluster (5 Brokers)"
        B1[Broker 1<br/>Leader - Partition 1]
        B2[Broker 2<br/>Leader - Partition 2]
        B3[Broker 3<br/>Leader - Partition 3]
        B4[Broker 4<br/>Replica]
        B5[Broker 5<br/>Replica]
        
        %% Replication connections
        B1 --- B4
        B1 --- B5
        B2 --- B4
        B2 --- B5
        B3 --- B4
        B3 --- B5
    end

    subgraph "Client A Consumer Group Cluster"
        CG1[Consumer Group A]
        
        subgraph "Group A Consumers"
            CA1[Consumer A1]
            CA2[Consumer A2]
            CA3[Consumer A3]
            CA4[Consumer A4]
            CA5[Consumer A5]
        end
    end

    subgraph "Client B Consumer Group Cluster"
        CG2[Consumer Group B]
        
        subgraph "Group B Consumers"
            CB1[Consumer B1]
            CB2[Consumer B2]
            CB3[Consumer B3]
            CB4[Consumer B4]
            CB5[Consumer B5]
        end
    end

    %% Producer connections with topic routing
    P1 -->|Topic A| B1
    P1 -->|Topic A| B2
    P2 -->|Topic B| B2
    P2 -->|Topic B| B3
    P3 -->|Topic A & B| B1
    P3 -->|Topic A & B| B3

    %% Consumer Group connections
    CG1 --> CA1
    CG1 --> CA2
    CG1 --> CA3
    CG1 --> CA4
    CG1 --> CA5

    CG2 --> CB1
    CG2 --> CB2
    CG2 --> CB3
    CG2 --> CB4
    CG2 --> CB5

    %% Consumer connections to brokers with topic isolation
    CA1 -->|Topic A| B1
    CA2 -->|Topic A| B2
    CA3 -->|Topic A| B3
    CA4 -->|Topic A| B4
    CA5 -->|Topic A| B5

    CB1 -->|Topic B| B1
    CB2 -->|Topic B| B2
    CB3 -->|Topic B| B3
    CB4 -->|Topic B| B4
    CB5 -->|Topic B| B5

    classDef broker fill:#f9f,stroke:#333,stroke-width:2px
    classDef producer fill:#bbf,stroke:#333,stroke-width:2px
    classDef consumer fill:#bfb,stroke:#333,stroke-width:2px
    classDef group fill:#fff,stroke:#333,stroke-width:2px

    class B1,B2,B3,B4,B5 broker
    class P1,P2,P3 producer
    class CA1,CA2,CA3,CA4,CA5,CB1,CB2,CB3,CB4,CB5 consumer
    class CG1,CG2 group