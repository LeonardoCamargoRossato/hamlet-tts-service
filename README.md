# Hamlet TTS Service (FastAPI + Piper)

Microservico HTTP para TTS do projeto Hamlet. O frontend nunca chama este servico diretamente: a chamada deve vir da Edge Function `hamlet-tts`.

## Arquitetura V1

- Frontend (Lovable) -> Edge Function `hamlet-tts` -> FastAPI TTS Service
- FastAPI valida payload + token Bearer
- Piper gera WAV a partir de texto
- Opcionalmente converte para MP3 com `ffmpeg`
- Resposta retorna audio binario (`audio/wav` ou `audio/mpeg`)

## Endpoints

- `GET /` — informacoes do servico (evita `Not Found` ao abrir a URL raiz no navegador)
- `GET /health` — health check (use para **prewarm** no Render Free)
- `POST /tts` — gera audio (Bearer obrigatorio)

## Latencia, Render Free e audio “estranho”

### Cold start no plano Free (ate ~1 min antes de responder)

No **Free**, a instancia **hiberna** apos inatividade. O primeiro request depois disso pode levar **dezenas de segundos** so para **acordar** o container — isso **nao** e bug do Piper; e limite do plano. O aviso aparece no proprio painel do Render.

**O que melhora de verdade a experiencia:**

1. **Plano pago (Starter ou superior)** no mesmo Web Service — a instancia deixa de hibernar como no Free e a latencia volta a ser sobretudo **geracao TTS** (segundos, nao minuto).
2. **Prewarm na Edge Function**: quando o usuario **abre o chat**, faca um `GET /health` no microservico (com timeout curto). Isso “acorda” o servico **antes** do primeiro `/tts`.
3. **Feedback no UI**: mostrar “Gerando voz…” **no mesmo instante** em que a Edge Function chama o TTS, para o usuario nao achar que travou.

### Geracao (apos o servico ja estar acordado)

Para **1–4 paragrafos**, o tempo dominante e **Piper + MP3**. A API usa **MP3 em mono com bitrate fixo** (`MP3_BITRATE`, padrao `96k`) para **encode mais rapido** que o perfil VBR anterior.

Variaveis uteis no Render:

| Variavel | Efeito |
|----------|--------|
| `PIPER_TIMEOUT_SECONDS` | Padrao **600** — sintese em CPU fraca pode demorar em textos longos |
| `FFMPEG_TIMEOUT_SECONDS` | Padrao **300** — conversao MP3 |
| `REQUEST_TIMEOUT_SECONDS` | Opcional **legado**: se setado e os dois acima nao, vale para Piper e ffmpeg |
| `MP3_BITRATE` | Ex.: `80k` (mais leve/rapido) ou `128k` (mais qualidade) |

### Audio corrompido / “carregou errado” no player

Se o `.mp3` toca errado ou quebra no meio:

1. Na **Edge Function**, a resposta do `/tts` tem que ser tratada como **binario** (`arrayBuffer()` / `Uint8Array`), **nunca** como texto (`text()` / `json()`), senao o arquivo corrompe.
2. Confira se nao ha **timeout** menor que o tempo de geracao (Lovable/Supabase costuma ter limite por invocacao).
3. Teste com `"format":"wav"` para isolar se o problema e o passo MP3 ou o Piper.

Payload de exemplo:

```json
{
  "text": "Texto para narrar",
  "voice": "pt_BR-faber-medium",
  "length_scale": 1.0,
  "format": "mp3"
}
```

Header obrigatorio:

```txt
Authorization: Bearer <API_TOKEN>
```

## Variaveis de ambiente

Copie:

```bash
cp .env.example .env
```

Edite pelo menos:

- `API_TOKEN`: token compartilhado com a Edge Function
- `DEFAULT_VOICE`: voz padrao (ex: `pt_BR-faber-medium`)

## Baixar modelo PT-BR

Para **Docker/Render**, nao e obrigatorio commitar o `.onnx`: se o arquivo `models/pt_BR-faber-medium.onnx` nao existir, o **build da imagem** baixa a voz automaticamente (ver `Dockerfile`).

Para desenvolvimento local **sem** depender do download no build, crie a pasta e baixe os dois arquivos da voz:

```bash
mkdir -p models

curl -L -o models/pt_BR-faber-medium.onnx \
https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx

curl -L -o models/pt_BR-faber-medium.onnx.json \
https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json
```

## Rodar local com Docker Compose

```bash
docker compose up --build
```

Teste:

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST "http://localhost:8000/tts" \
  -H "Authorization: Bearer change-this-token" \
  -H "Content-Type: application/json" \
  -d '{
    "text":"Ola, eu sou o Hamlet.",
    "voice":"pt_BR-faber-medium",
    "length_scale":1.0,
    "format":"mp3"
  }' \
  --output hamlet.mp3
```

## Deploy no Render (recomendado para este repo)

Este servico esta preparado para deploy como **Web Service com Docker** no Render:

- `Dockerfile` na raiz (build remoto baixa Piper + modelo PT-BR no build)
- `render.yaml` (Blueprint) para criar o servico por IaC
- Porta HTTP via variavel `PORT` (Render injeta automaticamente; o CMD ja usa `${PORT}`)
- Health check em `GET /health`

### Pre-requisitos

1. Conta no [Render](https://render.com) e repositorio Git (GitHub/GitLab/Bitbucket) com este codigo publicado.

2. **Memoria**: Piper + modelo ONNX costuma precisar de mais que o tier gratuito permite em alguns casos. Se o deploy falhar por OOM ou build lento, suba para um plano com mais RAM (ex.: Starter).

### Build falhou no plano Free (status 1)

Se o log para durante `apt-get install` com muitas bibliotecas (antes de Piper/HF), costuma ser **falta de RAM no build** ao instalar pacotes pesados. Este `Dockerfile` **nao** usa mais `apt install ffmpeg` (que puxa OpenGL/audio demais); usa **ffmpeg estatico** so para MP3. Atualize o repo e rode **Manual Deploy** de novo.

Sempre role o **Build log** ate o **ultimo erro em vermelho**; a causa real costuma estar no fim, nao no meio do `apt`.

### Opcao A — Blueprint (`render.yaml`)

1. No Render: **New +** → **Blueprint**.
2. Conecte o repositorio que contem este projeto na raiz.
3. O Render detecta `render.yaml` e lista o servico `hamlet-tts`.
4. No fluxo de aplicacao do Blueprint, quando pedir **`API_TOKEN`**, defina um segredo forte (o mesmo que voce colocara na Edge Function).
5. **Apply** e aguarde o build + deploy.

Apos o deploy, anote a URL publica (ex.: `https://hamlet-tts.onrender.com`).

### Opcao B — Web Service manual (sem Blueprint)

1. **New +** → **Web Service**.
2. Conecte o repo; **Runtime**: **Docker**.
3. **Dockerfile Path**: `Dockerfile` (raiz). **Docker Build Context Directory**: `.` (raiz).
4. **Health Check Path**: `/health`.
5. Em **Environment**, adicione pelo menos:

| Variavel           | Valor |
|--------------------|--------|
| `API_TOKEN`        | Mesmo token que a Edge Function envia no header `Authorization` |
| `PIPER_BIN`        | `/opt/piper/piper` (opcional; ja e o padrao no codigo) |
| `MODELS_DIR`       | `/app/models` |
| `DEFAULT_VOICE`    | `pt_BR-faber-medium` |
| `DEFAULT_FORMAT`   | `mp3` |

**Nao** defina `PORT` manualmente — o Render define.

### Build da imagem e modelo de voz

- O **binario Piper** e baixado no `Dockerfile` a partir do release oficial (GitHub).
- Se `models/pt_BR-faber-medium.onnx` **nao** existir no repo, o build **baixa automaticamente** o par `.onnx` + `.onnx.json` do Hugging Face (ideal para Render sem commit de arquivos grandes).

Para **desativar** o download no build (build offline com modelos locais):

```bash
docker build --build-arg DOWNLOAD_DEFAULT_VOICE=0 -t hamlet-tts .
```

### Verificacao pos-deploy

Substitua a URL e o token:

```bash
curl -sS "https://SEU-SERVICO.onrender.com/health"
```

```bash
curl -sS -X POST "https://SEU-SERVICO.onrender.com/tts" \
  -H "Authorization: Bearer SEU_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Teste Hamlet no Render.","voice":"pt_BR-faber-medium","length_scale":1.0,"format":"mp3"}' \
  --output teste.mp3
```

### Edge Function (`hamlet-tts`)

- URL base: `https://SEU-SERVICO.onrender.com`
- Chamar `POST /tts` com body JSON igual ao exemplo local.
- Encaminhar `Authorization: Bearer <API_TOKEN>` (ou montar esse header no servidor da Edge Function com o segredo guardado nas env vars do Lovable/Render).

### Outros provedores (referencia)

- **Railway / Fly.io**: o mesmo `Dockerfile` funciona; ajuste apenas env vars e porta conforme o provedor.

## Integracao com Edge Function

- A Edge Function deve:
  - Injetar `Authorization: Bearer <API_TOKEN>`
  - Enviar JSON para `/tts`
  - Repassar o binario de audio para o cliente
- O frontend continua desacoplado do provedor TTS

## Proximos passos recomendados

- Limite de taxa por token/IP
- Observabilidade (logs estruturados + metricas)
- Suporte a multiplas vozes/modelos por ambiente
- Opcao de streaming de audio
