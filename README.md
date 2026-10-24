# Aprova Command

Hackathon GovTech Aprova — **Desafio 2: coletar e validar a regra de negócio de ~100 processos sem depender de reunião.**

Aplicação web local que coordena a validação de formulários municipais a partir de tickets. Um caso persistente por ticket conduz o processo até uma versão **testada, aprovada pelas duas partes, aplicada e verificada**. O implantador vê "o que fazer hoje" e a prefeitura responde e aprova num **Portal** simples, no mesmo caso que Pylon e WhatsApp.

> **Ambiente de demonstração — dados sintéticos.** IA em modo *replay offline* (gravações identificadas); extração de anexos simulada. Nenhum número local representa impacto em prefeituras reais.

## Situação

| Fatia (plano v2 §17) | Estado |
|---|---|
| 1. Ciclo completo estreito (cenário G) | **Implementada e testada** (backend: testes; ciclo verificado pela UI) |
| 2. Intake e rodadas multicanal (Pylon/WhatsApp/Portal) | Não iniciada |
| 3. Exceções, anexos e responsáveis | Não iniciada |
| 4. Generalização medida (inferência ao vivo) | Não iniciada — cenário F `not_run` |
| 5. Demo completa (140 processos, cronograma, métricas) | Não iniciada |

Pendências conhecidas da fatia 1: migrações Alembic (hoje `create_all`), E2E Playwright, geração de tipos pelo OpenAPI, Caixa de entrada.

## Como rodar (Windows)

Pré-requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 24.

```powershell
cd backend;  uv sync          # dependências do backend
cd ..\frontend; npm install   # dependências do frontend
cd ..; .\scripts\dev.ps1      # API em :8000 (com worker) + app em :5173
```

Abra http://127.0.0.1:5173, escolha **Rui Prado (implantador)**, vá em *Demonstração* → **Iniciar cenário G**.

`.\scripts\verify.ps1` roda os testes do backend e o build do frontend.

## Cenário G (o que a demo mostra)

1. Ticket com dois pedidos claros → o agente (replay) separa as intenções, **cita o trecho literal** e propõe a candidata com testes positivo, negativo e de limite.
2. O implantador revisa os resultados esperados dos testes e pede a aprovação.
3. **Ana (prefeitura)** abre o Portal, vê em linguagem simples o que muda e exemplos, e aprova a versão exata.
4. **Rui (Aprova)** dá a segunda aprovação (pessoa distinta, papel validado no servidor).
5. Aplicação com compare-and-swap da versão-base, recibo único, **read-back** do motor com os testes, nota interna e fechamento.

Editar a candidata/testes invalida as duas aprovações; outra alteração na base vigente bloqueia a aplicação (`BASE_VERSION_CONFLICT`).

## Arquitetura

- **Backend** (`backend/app`): `domain/` (formulário, condições, ChangeSet, hash canônico, máquina de estados — sem I/O), `application/` (casos, aprovações, aplicação, projeções Hoje/Portal), `agent/` (contratos fechados, replay, loader de instruções), `worker/` (leases com token, retry 1s/5s), `api/` (FastAPI, `Idempotency-Key`, erros padronizados). SQLite em WAL.
- **Frontend** (`frontend/src`): React + TypeScript + Vite + Tailwind v4 + **shadcn/ui**; tokens do [direcionamento visual](Kimi_Agent_Age%20of%20Empires%20Municipal/direcionamento%20visual.md); componentes de domínio em `components/domain`.
- **IA ≠ autoridade**: o agente só propõe; o backend valida citações/catálogo e decide transições e efeitos. Ver [`INSTRUCTIONS.md`](INSTRUCTIONS.md) e a pasta [`INSTRUCTIONS/`](INSTRUCTIONS/).

## Documentos

- Plano: `Kimi_Agent_Age of Empires Municipal/Aprova Command — Plano consolidado de implementação v2.md`
- Adendo (Portal, Hoje, shadcn): `.../Aprova Command — Adendo v2.1 Portal, Hoje e shadcn.md`

## Limitações

Personas livres (não é autenticação); Portal acessado por troca de persona, sem link mágico ainda; sem integrações reais com Pylon/WhatsApp/Aprova; sem inferência ao vivo.
