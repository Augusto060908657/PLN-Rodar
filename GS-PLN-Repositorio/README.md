# Zelador: assistente de voz de zeladoria urbana (CitizenTech, GS 2027 PLN)

**Integrante (trabalho individual):** Octavio Augusto Ramalho Brandão Pires, RM 555696
**Vídeo de demonstração (até 5 minutos):** https://youtu.be/bQPZ1kpIc0I
**Relatório:** [`relatorio_zelador.pdf`](relatorio_zelador.pdf)

O cidadão **fala** um problema urbano (buraco, árvore, lâmpada queimada, bueiro, entulho, calçada, semáforo). O assistente transcreve a fala (STT), entende com um LLM, faz as perguntas que faltam (tipo, local, gravidade), confirma e gera um **protocolo simulado**, orientando o pedido oficial no SP156. A resposta é falada (TTS), e a transcrição e o texto aparecem na tela.

- **Persona:** Dona Helena, 68 anos, usa o celular só para ligar e mandar áudio, vê um buraco na rua e não sabe como pedir o conserto.
- **ODS:** 11 (Cidades e Comunidades Sustentáveis, meta 11.7), secundariamente ODS 10.
- **Protótipo acadêmico:** não envia pedidos reais à Prefeitura.

## Arquitetura
`microfone/upload → STT (faster-whisper) → diálogo (memória + salvaguardas + RAG) → LLM (Qwen2.5 via Ollama) → adaptação para fala → TTS (Piper) → alto-falante`, com interface Gradio e registro de latência por etapa. Diagrama e justificativas (por que local/Colab e sem API, por que RAG) estão no relatório.

| Módulo | Arquivo |
|---|---|
| STT | `src/stt.py` |
| Diálogo, memória e protocolo simulado | `src/dialogo.py` |
| Base de conhecimento (RAG com TF-IDF) | `src/rag.py` e `dados/base_conhecimento/` |
| Emergências, saúde e apoio emocional | `src/guardrails.py` |
| LLM (Ollama) | `src/llm.py` |
| Adaptação para fala | `src/fala.py` |
| TTS (Piper) | `src/tts.py` |
| Pipeline e latência por etapa | `src/pipeline.py` |
| Interface (Gradio) | `src/app_gradio.py` |
| LGPD (aviso e retenção mínima) | `src/lgpd.py`, `src/config.py` |
| Avaliações e relatório | `src/avaliacao_*.py`, `src/reavaliar_llm.py`, `src/analise_vies.py`, `src/gerar_planilhas.py`, `src/gerar_relatorio.py` |

## Estrutura do repositório
- `GS_PLN_Entrega.ipynb`: notebook do Colab, já executado (com as saídas).
- `src/`, `requirements.txt`: código.
- `audios_teste/`: os 24 áudios gravados pelo grupo (6 vozes, 6 com ruído) e 2 regravações (`_RETAKE`).
- `dados/`: base de conhecimento, frases de referência do STT, `perguntas_llm.csv` (30 perguntas com resposta esperada), `roteiros_conversas.csv` (10 conversas), `frases_tts.csv`, `notas_tts.csv`, roteiro de gravação e modelo de autorização de voz.
- `planilhas/`: planilhas de avaliação de STT, LLM e TTS (com fórmulas).
- `resultados/`: CSVs das medições, figura, amostras do TTS e a execução anterior do LLM.

## Como executar
**Colab (GPU T4):**
1. Abra `GS_PLN_Entrega.ipynb` no Google Colab e escolha *Ambiente de execução → Alterar tipo → GPU T4*.
2. Execute as células na ordem. A seção 0 baixa este repositório (variável `REPO_URL`) e confere a versão do projeto (`__versao__` em `src/__init__.py`).
3. Seções 3 a 6: avaliações de STT, LLM, TTS e ponta a ponta. Seção 7: demonstração com microfone e upload (Gradio). Seção 8: planilhas e relatório com os números.

**Local (Linux/macOS/WSL):** `pip install -r requirements.txt`, instale o ffmpeg e o Ollama (`ollama pull qwen2.5:7b`), e rode `python -m src.app_gradio`. A voz do Piper é baixada sozinha para `modelos/piper/` na primeira vez. Em máquinas fracas use `--stt-modelo small --llm qwen2.5:3b`.

## Problemas comuns
| Sintoma | Causa e solução |
|---|---|
| Gradio mostra "Erro" nas três caixas; log com `TypeError: open() got an unexpected keyword argument 'metadata_errors'` | O PyAV (`av`) 19.x não aceita mais um argumento que o faster-whisper usa. Corrigido de três formas: `requirements.txt` fixa `av<19`; o STT (`src/stt.py`) decodifica o áudio com ffmpeg e nem chama o `av`; `src/__init__.py` tem um remendo de segurança. Se o erro voltar, reinicie a sessão do Colab e rode da seção 0. |
| Notebook usa código antigo depois de reiniciar | A pasta `/content` do Colab sobrevive ao reinício. A seção 0 confere `__versao__` e troca a cópia antiga pela atual. |
| Demora minutos na primeira resposta | O Ollama carrega o modelo de 7B na GPU na primeira chamada. A demo já faz esse aquecimento antes de abrir a interface. |
| `libcudnn` / `libcublas` não encontrada | A seção 1 instala `nvidia-cublas-cu12` e `nvidia-cudnn-cu12`; o `src/stt.py` carrega essas bibliotecas dentro do processo. Sem elas, o STT cai sozinho para CPU (funciona, mas é bem mais lento). |
| "Não consegui falar com o Ollama" | O servidor não está de pé: rode `ollama serve` (no Colab, execute a célula da seção 1 ou 7). |
| "O modelo ... não está baixado" | Rode `ollama pull qwen2.5:7b` (e `qwen2.5:3b` para a comparação). |

## Modelos, versões e licenças
| Componente | Uso | Licença |
|---|---|---|
| Whisper small e medium (OpenAI), via faster-whisper 1.2.1 e CTranslate2 4.9.0 | STT na GPU (float16) | MIT |
| Whisper base, small e medium em ONNX int8 (sherpa-onnx) | medições de referência em CPU (`resultados/stt_base.csv`, `stt_small.csv`, `stt_medium.csv`) | MIT |
| Qwen2.5-7B-Instruct (Ollama, `qwen2.5:7b`) | LLM principal | Apache-2.0 |
| Qwen2.5-3B-Instruct (Ollama, `qwen2.5:3b`) | LLM de comparação | Qwen Research License (uso não comercial) |
| Piper `pt_BR-faber-medium`, piper-tts 1.8.0 | TTS, voz sintética pronta, sem clonagem | piper-tts: GPL-3.0-or-later; a licença da voz está no model card (rhasspy/piper-voices), a conferir |
| Gradio 5.50.0, jiwer, scikit-learn, num2words, Ollama | interface, WER, RAG, números por extenso, servidor do LLM | Apache-2.0, Apache-2.0, BSD, LGPL, MIT |

## Resultados (medidos no Colab, GPU T4)
**STT, 24 áudios, 6 vozes, 6 com ruído (faster-whisper), comparação small × medium:**

| Whisper | WER médio | WER limpo | WER ruído | Tempo médio |
|---|---|---|---|---|
| small | 8,0% | 8,5% | 6,3% | 0,37 s |
| **medium (escolhido)** | **5,0%** | 4,7% | 5,7% | 0,60 s |

Referência em CPU (ONNX): base 25,1%, small 9,6%, medium 4,8%.

**LLM, 30 perguntas (15 do tema, 5 de continuação, 5 fora do escopo, 5 de emergência/limites), 7B × 3B:**

| Modelo | Critério inicial | Critério revisado | Fora do escopo (recusa) | Tempo médio do LLM |
|---|---|---|---|---|
| qwen2.5:7b (escolhido) | 17/30 (56,7%) | 21/30 (70,0%) | 5/5 | 1,37 s |
| qwen2.5:3b | 21/30 (70,0%) | 22/30 (73,3%) | 5/5 | 1,21 s |

O critério revisado reavalia as **mesmas respostas** com marcadores de recusa mais completos e palavras proibidas contra prazos inventados (`python -m src.reavaliar_llm`). Em uma execução anterior do mesmo código os totais revisados foram 23 (7B) e 23 (3B): a diferença entre os modelos está dentro da variação entre execuções, então a escolha do 7B se apoia na licença Apache-2.0 e no uso em todo o restante do projeto (ver relatório).

**TTS, 10 respostas, 4 avaliadores (`dados/notas_tts.csv`):** naturalidade média 3,12 e clareza média 4,15 (escala de 1 a 5). Latência média de síntese: 0,52 s.

**Ponta a ponta, 10 conversas (31 turnos, falas dos usuários sintetizadas), latência média em segundos:** STT 0,53 | RAG 0,00 | LLM 1,30 | adaptação para fala 0,00 | TTS 1,11 | **total até o áudio 2,95**.

## Limitações conhecidas
- O 7B acertou 8 das 15 perguntas do tema: em várias respostas ele pergunta "Posso registrar o pedido?" em vez de informar o SP156.
- A detecção do "sim" de confirmação é simples: em um teste, "Isso é urgente?" foi tomada como confirmação e gerou um protocolo.
- Não há regra fixa para pedidos jurídicos; os dois modelos falharam na pergunta sobre processar a prefeitura.
- 6 vozes e 4 áudios por pessoa, sem perfil (gênero, idade, sotaque): a análise de viés do STT é só por pessoa e condição.
- Os modelos de linguagem variam entre execuções (até 2 respostas de diferença em 30).

## Ética, segurança e LGPD
Aviso e aceite antes do uso; áudio apagado logo após a transcrição; nada enviado a APIs externas; o assistente não pede CPF nem dados pessoais; regras fixas para emergências e apoio emocional; resposta "não sei" quando falta informação; nenhuma clonagem de voz (voz sintética pronta do Piper). O modelo de autorização de uso da voz dos participantes está em `dados/modelo_autorizacao_voz.txt`.
