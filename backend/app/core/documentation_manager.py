"""Sistema de documentação interativa avançado.

Este módulo implementa:
- Documentação API automática (OpenAPI/Swagger)
- Documentação interativa com exemplos
- Guias de troubleshooting automáticos
- Tutoriais passo-a-passo
- Sistema de ajuda contextual
- Documentação versionada
- Geração automática de changelog
- Busca inteligente na documentação
- Feedback e avaliação de documentos
- Métricas de uso da documentação
"""

import asyncio
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union, Tuple

import aiofiles
import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


class DocumentType(Enum):
    """Tipos de documento."""
    API_REFERENCE = "api_reference"
    TUTORIAL = "tutorial"
    GUIDE = "guide"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    CHANGELOG = "changelog"
    GETTING_STARTED = "getting_started"
    EXAMPLES = "examples"
    ARCHITECTURE = "architecture"
    DEPLOYMENT = "deployment"


class DocumentStatus(Enum):
    """Status do documento."""
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class DocumentationConfig(BaseModel):
    """Configuração do sistema de documentação."""
    # Configurações gerais
    project_name: str = "MegaEmu Modern"
    project_version: str = "1.0.0"
    project_description: str = "Sistema moderno de gerenciamento de ROMs"
    
    # Diretórios
    docs_dir: str = "docs"
    templates_dir: str = "docs/templates"
    output_dir: str = "docs/build"
    static_dir: str = "docs/static"
    
    # API Documentation
    api_title: str = "MegaEmu Modern API"
    api_description: str = "API REST para gerenciamento de ROMs e jogos"
    api_version: str = "v1"
    openapi_url: str = "/openapi.json"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    
    # Geração automática
    auto_generate_api_docs: bool = True
    auto_generate_changelog: bool = True
    auto_update_examples: bool = True
    
    # Versionamento
    versioned_docs: bool = True
    keep_versions: int = 5
    
    # Busca
    search_enabled: bool = True
    search_index_file: str = "search_index.json"
    
    # Feedback
    feedback_enabled: bool = True
    analytics_enabled: bool = True
    
    # Temas
    theme: str = "default"
    custom_css: Optional[str] = None
    
    # Idiomas
    default_language: str = "pt-BR"
    supported_languages: List[str] = ["pt-BR", "en-US"]


class Document(BaseModel):
    """Documento."""
    id: str
    title: str
    type: DocumentType
    status: DocumentStatus
    content: str
    metadata: Dict[str, Any] = {}
    tags: List[str] = []
    version: str = "1.0.0"
    language: str = "pt-BR"
    author: str = ""
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    parent_id: Optional[str] = None  # Para documentos hierárquicos
    order: int = 0  # Para ordenação
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class APIEndpoint(BaseModel):
    """Endpoint da API."""
    path: str
    method: str
    summary: str
    description: str
    tags: List[str] = []
    parameters: List[Dict[str, Any]] = []
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Dict[str, Any]] = {}
    examples: List[Dict[str, Any]] = []
    deprecated: bool = False


class TutorialStep(BaseModel):
    """Passo de tutorial."""
    id: str
    title: str
    description: str
    code_example: Optional[str] = None
    language: str = "python"
    expected_output: Optional[str] = None
    tips: List[str] = []
    common_errors: List[Dict[str, str]] = []
    next_steps: List[str] = []


class Tutorial(BaseModel):
    """Tutorial."""
    id: str
    title: str
    description: str
    difficulty: str  # beginner, intermediate, advanced
    estimated_time: str  # "30 minutes"
    prerequisites: List[str] = []
    learning_objectives: List[str] = []
    steps: List[TutorialStep] = []
    resources: List[Dict[str, str]] = []
    tags: List[str] = []


class TroubleshootingIssue(BaseModel):
    """Issue de troubleshooting."""
    id: str
    title: str
    description: str
    symptoms: List[str] = []
    causes: List[str] = []
    solutions: List[Dict[str, Any]] = []  # {"title": "", "steps": [], "code": ""}
    related_issues: List[str] = []
    severity: str = "medium"  # low, medium, high, critical
    frequency: str = "common"  # rare, uncommon, common, frequent
    tags: List[str] = []


class SearchResult(BaseModel):
    """Resultado de busca."""
    document_id: str
    title: str
    type: DocumentType
    excerpt: str
    score: float
    url: str
    highlights: List[str] = []


class DocumentationMetrics(BaseModel):
    """Métricas da documentação."""
    total_documents: int = 0
    total_views: int = 0
    total_searches: int = 0
    popular_documents: List[Dict[str, Any]] = []
    search_queries: List[Dict[str, Any]] = []
    user_feedback: Dict[str, int] = {}
    avg_rating: float = 0.0
    completion_rates: Dict[str, float] = {}  # Para tutoriais


class CodeExampleGenerator:
    """Gerador de exemplos de código."""
    
    def __init__(self):
        self.templates = {
            "python": {
                "api_request": '''
# Exemplo de requisição à API
import requests
import json

# Configuração
api_base_url = "https://api.megaemu.com/v1"
api_key = "your_api_key_here"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# {description}
response = requests.{method}(
    f"{api_base_url}{path}",
    headers=headers{request_body}
)

if response.status_code == 200:
    data = response.json()
    print(json.dumps(data, indent=2))
else:
    print(f"Erro: {response.status_code} - {response.text}")
''',
                "async_request": '''
# Exemplo assíncrono
import aiohttp
import asyncio
import json

async def {function_name}():
    api_base_url = "https://api.megaemu.com/v1"
    api_key = "your_api_key_here"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.{method}(
            f"{api_base_url}{path}",
            headers=headers{request_body}
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(json.dumps(data, indent=2))
                return data
            else:
                error_text = await response.text()
                print(f"Erro: {response.status} - {error_text}")
                return None

# Executa a função
if __name__ == "__main__":
    asyncio.run({function_name}())
'''
            },
            "javascript": {
                "api_request": '''
// Exemplo de requisição à API
const apiBaseUrl = "https://api.megaemu.com/v1";
const apiKey = "your_api_key_here";

const headers = {
    "Authorization": `Bearer ${apiKey}`,
    "Content-Type": "application/json"
};

// {description}
fetch(`${apiBaseUrl}{path}`, {
    method: "{method}",
    headers: headers{request_body}
})
.then(response => {
    if (response.ok) {
        return response.json();
    }
    throw new Error(`HTTP error! status: ${response.status}`);
})
.then(data => {
    console.log(JSON.stringify(data, null, 2));
})
.catch(error => {
    console.error("Erro:", error);
});
''',
                "async_request": '''
// Exemplo assíncrono com async/await
const apiBaseUrl = "https://api.megaemu.com/v1";
const apiKey = "your_api_key_here";

async function {function_name}() {
    const headers = {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json"
    };
    
    try {
        const response = await fetch(`${apiBaseUrl}{path}`, {
            method: "{method}",
            headers: headers{request_body}
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log(JSON.stringify(data, null, 2));
            return data;
        } else {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error("Erro:", error);
        return null;
    }
}

// Executa a função
{function_name}();
'''
            },
            "curl": {
                "api_request": '''
# Exemplo com cURL
curl -X {method} \
  "{api_base_url}{path}" \
  -H "Authorization: Bearer your_api_key_here" \
  -H "Content-Type: application/json"{request_body}
'''
            }
        }
    
    def generate_api_example(
        self,
        endpoint: APIEndpoint,
        language: str = "python",
        style: str = "api_request"
    ) -> str:
        """Gera exemplo de código para endpoint da API."""
        if language not in self.templates:
            return f"# Exemplo não disponível para {language}"
        
        if style not in self.templates[language]:
            style = "api_request"
        
        template = self.templates[language][style]
        
        # Prepara dados para o template
        method = endpoint.method.lower()
        path = endpoint.path
        description = endpoint.description
        function_name = self._generate_function_name(endpoint)
        
        # Prepara request body se existir
        request_body = ""
        if endpoint.request_body and language in ["python", "javascript"]:
            if language == "python":
                if method in ["post", "put", "patch"]:
                    request_body = ",\n    json=data"
            elif language == "javascript":
                if method in ["post", "put", "patch"]:
                    request_body = ",\n    body: JSON.stringify(data)"
        elif endpoint.request_body and language == "curl":
            if method in ["post", "put", "patch"]:
                request_body = " \\
  -d '{\"example\": \"data\"}'"
        
        # Substitui variáveis no template
        return template.format(
            method=method,
            path=path,
            description=description,
            function_name=function_name,
            request_body=request_body,
            api_base_url="https://api.megaemu.com/v1"
        )
    
    def _generate_function_name(self, endpoint: APIEndpoint) -> str:
        """Gera nome de função baseado no endpoint."""
        # Remove parâmetros do path
        clean_path = re.sub(r'\{[^}]+\}', '', endpoint.path)
        # Remove caracteres especiais
        clean_path = re.sub(r'[^a-zA-Z0-9_]', '_', clean_path)
        # Remove underscores múltiplos
        clean_path = re.sub(r'_+', '_', clean_path).strip('_')
        
        method = endpoint.method.lower()
        
        if method == "get":
            prefix = "get"
        elif method == "post":
            prefix = "create"
        elif method == "put":
            prefix = "update"
        elif method == "delete":
            prefix = "delete"
        else:
            prefix = method
        
        return f"{prefix}_{clean_path}" if clean_path else prefix


class MarkdownProcessor:
    """Processador de Markdown."""
    
    def __init__(self):
        self.md = markdown.Markdown(
            extensions=[
                'codehilite',
                'fenced_code',
                'tables',
                'toc',
                'admonition',
                'attr_list',
                'def_list'
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': True
                },
                'toc': {
                    'permalink': True,
                    'title': 'Índice'
                }
            }
        )
    
    def process(self, content: str) -> Tuple[str, str]:
        """Processa Markdown e retorna HTML + TOC."""
        html = self.md.convert(content)
        toc = getattr(self.md, 'toc', '')
        
        # Reset para próximo uso
        self.md.reset()
        
        return html, toc
    
    def extract_headings(self, content: str) -> List[Dict[str, Any]]:
        """Extrai cabeçalhos do conteúdo."""
        headings = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                anchor = re.sub(r'[^a-zA-Z0-9_-]', '-', title.lower())
                
                headings.append({
                    'level': level,
                    'title': title,
                    'anchor': anchor,
                    'line': i + 1
                })
        
        return headings


class SearchEngine:
    """Motor de busca para documentação."""
    
    def __init__(self, config: DocumentationConfig):
        self.config = config
        self.index: Dict[str, Dict[str, Any]] = {}
        self.documents: Dict[str, Document] = {}
    
    def index_document(self, document: Document):
        """Indexa documento para busca."""
        self.documents[document.id] = document
        
        # Extrai texto para indexação
        text_content = self._extract_text(document.content)
        words = self._tokenize(text_content)
        
        # Cria índice invertido
        for word in words:
            if word not in self.index:
                self.index[word] = {}
            
            if document.id not in self.index[word]:
                self.index[word][document.id] = 0
            
            self.index[word][document.id] += 1
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Busca documentos."""
        query_words = self._tokenize(query.lower())
        
        if not query_words:
            return []
        
        # Calcula scores
        scores: Dict[str, float] = {}
        
        for word in query_words:
            if word in self.index:
                for doc_id, count in self.index[word].items():
                    if doc_id not in scores:
                        scores[doc_id] = 0
                    
                    # TF-IDF simplificado
                    tf = count
                    idf = len(self.documents) / len(self.index[word])
                    scores[doc_id] += tf * idf
        
        # Ordena por score
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Converte para SearchResult
        results = []
        for doc_id, score in sorted_results[:limit]:
            document = self.documents[doc_id]
            excerpt = self._generate_excerpt(document.content, query_words)
            highlights = self._generate_highlights(document.content, query_words)
            
            result = SearchResult(
                document_id=doc_id,
                title=document.title,
                type=document.type,
                excerpt=excerpt,
                score=score,
                url=f"/docs/{doc_id}",
                highlights=highlights
            )
            results.append(result)
        
        return results
    
    def _extract_text(self, content: str) -> str:
        """Extrai texto puro do conteúdo."""
        # Remove markdown
        text = re.sub(r'```[\s\S]*?```', '', content)  # Code blocks
        text = re.sub(r'`[^`]*`', '', text)  # Inline code
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Links
        text = re.sub(r'[#*_~`]', '', text)  # Markdown syntax
        
        return text
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokeniza texto."""
        # Remove pontuação e converte para minúsculas
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # Remove palavras muito curtas
        words = [w for w in words if len(w) > 2]
        
        return words
    
    def _generate_excerpt(self, content: str, query_words: List[str]) -> str:
        """Gera excerpt com contexto da busca."""
        text = self._extract_text(content)
        sentences = text.split('.')
        
        # Encontra sentença com mais palavras da query
        best_sentence = ""
        best_score = 0
        
        for sentence in sentences:
            sentence_words = self._tokenize(sentence)
            score = sum(1 for word in query_words if word in sentence_words)
            
            if score > best_score:
                best_score = score
                best_sentence = sentence.strip()
        
        # Limita tamanho
        if len(best_sentence) > 200:
            best_sentence = best_sentence[:200] + "..."
        
        return best_sentence or text[:200] + "..."
    
    def _generate_highlights(self, content: str, query_words: List[str]) -> List[str]:
        """Gera highlights das palavras encontradas."""
        text = self._extract_text(content)
        highlights = []
        
        for word in query_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            matches = pattern.findall(text)
            highlights.extend(matches)
        
        return list(set(highlights))  # Remove duplicatas
    
    def save_index(self, filepath: str):
        """Salva índice em arquivo."""
        index_data = {
            'index': self.index,
            'documents': {doc_id: doc.dict() for doc_id, doc in self.documents.items()}
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2, default=str)
    
    def load_index(self, filepath: str):
        """Carrega índice de arquivo."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            self.index = index_data.get('index', {})
            
            documents_data = index_data.get('documents', {})
            self.documents = {
                doc_id: Document(**doc_data)
                for doc_id, doc_data in documents_data.items()
            }
        except FileNotFoundError:
            pass


class DocumentationGenerator:
    """Gerador de documentação."""
    
    def __init__(self, config: DocumentationConfig):
        self.config = config
        self.code_generator = CodeExampleGenerator()
        self.markdown_processor = MarkdownProcessor()
        self.search_engine = SearchEngine(config)
        
        # Setup Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(config.templates_dir),
            autoescape=True
        )
        
        # Carrega índice de busca existente
        search_index_path = Path(config.output_dir) / config.search_index_file
        if search_index_path.exists():
            self.search_engine.load_index(str(search_index_path))
    
    async def generate_api_documentation(self, endpoints: List[APIEndpoint]) -> Document:
        """Gera documentação da API."""
        content_parts = [
            f"# {self.config.api_title}",
            "",
            self.config.api_description,
            "",
            f"**Versão:** {self.config.api_version}",
            "",
            "## Endpoints",
            ""
        ]
        
        # Agrupa endpoints por tag
        endpoints_by_tag = {}
        for endpoint in endpoints:
            for tag in endpoint.tags or ['Geral']:
                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []
                endpoints_by_tag[tag].append(endpoint)
        
        # Gera documentação para cada tag
        for tag, tag_endpoints in endpoints_by_tag.items():
            content_parts.extend([
                f"### {tag}",
                ""
            ])
            
            for endpoint in tag_endpoints:
                content_parts.extend([
                    f"#### {endpoint.method.upper()} {endpoint.path}",
                    "",
                    endpoint.description,
                    ""
                ])
                
                # Parâmetros
                if endpoint.parameters:
                    content_parts.extend([
                        "**Parâmetros:**",
                        "",
                        "| Nome | Tipo | Obrigatório | Descrição |",
                        "|------|------|-------------|-----------|"                    ])
                    
                    for param in endpoint.parameters:
                        required = "Sim" if param.get('required', False) else "Não"
                        content_parts.append(
                            f"| {param.get('name', '')} | {param.get('type', '')} | {required} | {param.get('description', '')} |"
                        )
                    
                    content_parts.append("")
                
                # Request body
                if endpoint.request_body:
                    content_parts.extend([
                        "**Request Body:**",
                        "",
                        "```json",
                        json.dumps(endpoint.request_body.get('example', {}), indent=2),
                        "```",
                        ""
                    ])
                
                # Responses
                if endpoint.responses:
                    content_parts.extend([
                        "**Responses:**",
                        ""
                    ])
                    
                    for status_code, response in endpoint.responses.items():
                        content_parts.extend([
                            f"**{status_code}** - {response.get('description', '')}",
                            ""
                        ])
                        
                        if 'example' in response:
                            content_parts.extend([
                                "```json",
                                json.dumps(response['example'], indent=2),
                                "```",
                                ""
                            ])
                
                # Exemplos de código
                content_parts.extend([
                    "**Exemplos:**",
                    "",
                    "=== \"Python\"",
                    "",
                    "```python",
                    self.code_generator.generate_api_example(endpoint, "python"),
                    "```",
                    "",
                    "=== \"JavaScript\"",
                    "",
                    "```javascript",
                    self.code_generator.generate_api_example(endpoint, "javascript"),
                    "```",
                    "",
                    "=== \"cURL\"",
                    "",
                    "```bash",
                    self.code_generator.generate_api_example(endpoint, "curl"),
                    "```",
                    "",
                    "---",
                    ""
                ])
        
        document = Document(
            id="api-reference",
            title=self.config.api_title,
            type=DocumentType.API_REFERENCE,
            status=DocumentStatus.PUBLISHED,
            content="\n".join(content_parts),
            metadata={
                "endpoints_count": len(endpoints),
                "tags": list(endpoints_by_tag.keys())
            },
            tags=["api", "reference"],
            version=self.config.api_version,
            language=self.config.default_language,
            author="system",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc)
        )
        
        return document
    
    async def generate_tutorial(self, tutorial: Tutorial) -> Document:
        """Gera documento de tutorial."""
        content_parts = [
            f"# {tutorial.title}",
            "",
            tutorial.description,
            "",
            f"**Dificuldade:** {tutorial.difficulty.title()}",
            f"**Tempo estimado:** {tutorial.estimated_time}",
            ""
        ]
        
        # Pré-requisitos
        if tutorial.prerequisites:
            content_parts.extend([
                "## Pré-requisitos",
                ""
            ])
            for prereq in tutorial.prerequisites:
                content_parts.append(f"- {prereq}")
            content_parts.append("")
        
        # Objetivos de aprendizado
        if tutorial.learning_objectives:
            content_parts.extend([
                "## O que você vai aprender",
                ""
            ])
            for objective in tutorial.learning_objectives:
                content_parts.append(f"- {objective}")
            content_parts.append("")
        
        # Passos
        content_parts.extend([
            "## Tutorial",
            ""
        ])
        
        for i, step in enumerate(tutorial.steps, 1):
            content_parts.extend([
                f"### Passo {i}: {step.title}",
                "",
                step.description,
                ""
            ])
            
            # Exemplo de código
            if step.code_example:
                content_parts.extend([
                    "```" + step.language,
                    step.code_example,
                    "```",
                    ""
                ])
            
            # Output esperado
            if step.expected_output:
                content_parts.extend([
                    "**Output esperado:**",
                    "",
                    "```",
                    step.expected_output,
                    "```",
                    ""
                ])
            
            # Dicas
            if step.tips:
                content_parts.extend([
                    "!!! tip \"Dicas\"",
                    ""
                ])
                for tip in step.tips:
                    content_parts.append(f"    - {tip}")
                content_parts.append("")
            
            # Erros comuns
            if step.common_errors:
                content_parts.extend([
                    "!!! warning \"Erros comuns\"",
                    ""
                ])
                for error in step.common_errors:
                    content_parts.extend([
                        f"    **{error.get('error', '')}**",
                        f"    {error.get('solution', '')}",
                        ""
                    ])
        
        # Próximos passos
        if tutorial.resources:
            content_parts.extend([
                "## Recursos adicionais",
                ""
            ])
            for resource in tutorial.resources:
                content_parts.append(f"- [{resource.get('title', '')}]({resource.get('url', '')})")
            content_parts.append("")
        
        document = Document(
            id=tutorial.id,
            title=tutorial.title,
            type=DocumentType.TUTORIAL,
            status=DocumentStatus.PUBLISHED,
            content="\n".join(content_parts),
            metadata={
                "difficulty": tutorial.difficulty,
                "estimated_time": tutorial.estimated_time,
                "steps_count": len(tutorial.steps)
            },
            tags=tutorial.tags + ["tutorial", tutorial.difficulty],
            version="1.0.0",
            language=self.config.default_language,
            author="system",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc)
        )
        
        return document
    
    async def generate_troubleshooting_guide(self, issues: List[TroubleshootingIssue]) -> Document:
        """Gera guia de troubleshooting."""
        content_parts = [
            "# Guia de Troubleshooting",
            "",
            "Este guia contém soluções para problemas comuns do MegaEmu Modern.",
            "",
            "## Índice de Problemas",
            ""
        ]
        
        # Índice
        for issue in issues:
            content_parts.append(f"- [{issue.title}](#{issue.id})")
        content_parts.append("")
        
        # Problemas por categoria
        issues_by_severity = {}
        for issue in issues:
            severity = issue.severity
            if severity not in issues_by_severity:
                issues_by_severity[severity] = []
            issues_by_severity[severity].append(issue)
        
        severity_order = ["critical", "high", "medium", "low"]
        severity_titles = {
            "critical": "🚨 Problemas Críticos",
            "high": "⚠️ Problemas de Alta Prioridade",
            "medium": "⚡ Problemas Comuns",
            "low": "💡 Problemas Menores"
        }
        
        for severity in severity_order:
            if severity in issues_by_severity:
                content_parts.extend([
                    f"## {severity_titles[severity]}",
                    ""
                ])
                
                for issue in issues_by_severity[severity]:
                    content_parts.extend([
                        f"### {issue.title} {{#{issue.id}}}",
                        "",
                        issue.description,
                        ""
                    ])
                    
                    # Sintomas
                    if issue.symptoms:
                        content_parts.extend([
                            "**Sintomas:**",
                            ""
                        ])
                        for symptom in issue.symptoms:
                            content_parts.append(f"- {symptom}")
                        content_parts.append("")
                    
                    # Possíveis causas
                    if issue.causes:
                        content_parts.extend([
                            "**Possíveis causas:**",
                            ""
                        ])
                        for cause in issue.causes:
                            content_parts.append(f"- {cause}")
                        content_parts.append("")
                    
                    # Soluções
                    if issue.solutions:
                        content_parts.extend([
                            "**Soluções:**",
                            ""
                        ])
                        
                        for i, solution in enumerate(issue.solutions, 1):
                            content_parts.extend([
                                f"**Solução {i}: {solution.get('title', '')}**",
                                ""
                            ])
                            
                            for step in solution.get('steps', []):
                                content_parts.append(f"1. {step}")
                            
                            if solution.get('code'):
                                content_parts.extend([
                                    "",
                                    "```bash",
                                    solution['code'],
                                    "```"
                                ])
                            
                            content_parts.append("")
                    
                    # Issues relacionados
                    if issue.related_issues:
                        content_parts.extend([
                            "**Veja também:**",
                            ""
                        ])
                        for related_id in issue.related_issues:
                            related_issue = next((i for i in issues if i.id == related_id), None)
                            if related_issue:
                                content_parts.append(f"- [{related_issue.title}](#{related_id})")
                        content_parts.append("")
                    
                    content_parts.extend([
                        "---",
                        ""
                    ])
        
        document = Document(
            id="troubleshooting-guide",
            title="Guia de Troubleshooting",
            type=DocumentType.TROUBLESHOOTING,
            status=DocumentStatus.PUBLISHED,
            content="\n".join(content_parts),
            metadata={
                "issues_count": len(issues),
                "severities": list(issues_by_severity.keys())
            },
            tags=["troubleshooting", "help", "problems"],
            version="1.0.0",
            language=self.config.default_language,
            author="system",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc)
        )
        
        return document
    
    async def render_document_html(self, document: Document) -> str:
        """Renderiza documento como HTML."""
        # Processa Markdown
        html_content, toc = self.markdown_processor.process(document.content)
        
        # Carrega template
        template = self.jinja_env.get_template('document.html')
        
        # Renderiza
        html = template.render(
            document=document,
            content=html_content,
            toc=toc,
            config=self.config
        )
        
        return html
    
    async def build_documentation_site(self, documents: List[Document]):
        """Constrói site de documentação."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Indexa documentos para busca
        for document in documents:
            self.search_engine.index_document(document)
        
        # Salva índice de busca
        search_index_path = output_dir / self.config.search_index_file
        self.search_engine.save_index(str(search_index_path))
        
        # Gera páginas HTML
        for document in documents:
            html = await self.render_document_html(document)
            
            # Salva arquivo HTML
            doc_file = output_dir / f"{document.id}.html"
            async with aiofiles.open(doc_file, 'w', encoding='utf-8') as f:
                await f.write(html)
        
        # Gera índice principal
        await self._generate_index_page(documents, output_dir)
        
        # Copia arquivos estáticos
        await self._copy_static_files(output_dir)
        
        print(f"📚 Documentação gerada em {output_dir}")
    
    async def _generate_index_page(self, documents: List[Document], output_dir: Path):
        """Gera página índice."""
        # Agrupa documentos por tipo
        docs_by_type = {}
        for doc in documents:
            doc_type = doc.type
            if doc_type not in docs_by_type:
                docs_by_type[doc_type] = []
            docs_by_type[doc_type].append(doc)
        
        # Carrega template
        template = self.jinja_env.get_template('index.html')
        
        # Renderiza
        html = template.render(
            documents_by_type=docs_by_type,
            config=self.config
        )
        
        # Salva
        index_file = output_dir / "index.html"
        async with aiofiles.open(index_file, 'w', encoding='utf-8') as f:
            await f.write(html)
    
    async def _copy_static_files(self, output_dir: Path):
        """Copia arquivos estáticos."""
        static_src = Path(self.config.static_dir)
        static_dst = output_dir / "static"
        
        if static_src.exists():
            if static_dst.exists():
                shutil.rmtree(static_dst)
            shutil.copytree(static_src, static_dst)


class DocumentationManager:
    """Gerenciador principal da documentação."""
    
    def __init__(self, config: DocumentationConfig):
        self.config = config
        self.generator = DocumentationGenerator(config)
        self.documents: Dict[str, Document] = {}
        self.metrics = DocumentationMetrics()
        
        # Cria diretórios necessários
        for dir_path in [config.docs_dir, config.templates_dir, config.output_dir, config.static_dir]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    async def add_document(self, document: Document):
        """Adiciona documento."""
        self.documents[document.id] = document
        self.metrics.total_documents = len(self.documents)
        
        # Indexa para busca
        self.generator.search_engine.index_document(document)
    
    async def update_document(self, document_id: str, updates: Dict[str, Any]) -> Optional[Document]:
        """Atualiza documento."""
        if document_id not in self.documents:
            return None
        
        document = self.documents[document_id]
        
        # Aplica atualizações
        for key, value in updates.items():
            if hasattr(document, key):
                setattr(document, key, value)
        
        document.updated_at = datetime.now(timezone.utc)
        
        # Re-indexa
        self.generator.search_engine.index_document(document)
        
        return document
    
    async def delete_document(self, document_id: str) -> bool:
        """Remove documento."""
        if document_id in self.documents:
            del self.documents[document_id]
            self.metrics.total_documents = len(self.documents)
            return True
        return False
    
    def search_documents(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Busca documentos."""
        self.metrics.total_searches += 1
        return self.generator.search_engine.search(query, limit)
    
    async def generate_api_docs(self, endpoints: List[APIEndpoint]):
        """Gera documentação da API."""
        if self.config.auto_generate_api_docs:
            document = await self.generator.generate_api_documentation(endpoints)
            await self.add_document(document)
            return document
    
    async def generate_tutorial_docs(self, tutorials: List[Tutorial]):
        """Gera documentação de tutoriais."""
        generated_docs = []
        for tutorial in tutorials:
            document = await self.generator.generate_tutorial(tutorial)
            await self.add_document(document)
            generated_docs.append(document)
        return generated_docs
    
    async def generate_troubleshooting_docs(self, issues: List[TroubleshootingIssue]):
        """Gera documentação de troubleshooting."""
        document = await self.generator.generate_troubleshooting_guide(issues)
        await self.add_document(document)
        return document
    
    async def build_site(self):
        """Constrói site de documentação."""
        published_docs = [
            doc for doc in self.documents.values()
            if doc.status == DocumentStatus.PUBLISHED
        ]
        
        await self.generator.build_documentation_site(published_docs)
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """Obtém documento por ID."""
        return self.documents.get(document_id)
    
    def list_documents(
        self,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        tags: Optional[List[str]] = None
    ) -> List[Document]:
        """Lista documentos com filtros."""
        docs = list(self.documents.values())
        
        if document_type:
            docs = [doc for doc in docs if doc.type == document_type]
        
        if status:
            docs = [doc for doc in docs if doc.status == status]
        
        if tags:
            docs = [
                doc for doc in docs
                if any(tag in doc.tags for tag in tags)
            ]
        
        # Ordena por data de atualização
        docs.sort(key=lambda x: x.updated_at, reverse=True)
        
        return docs
    
    def get_metrics(self) -> DocumentationMetrics:
        """Obtém métricas da documentação."""
        return self.metrics
    
    async def record_view(self, document_id: str):
        """Registra visualização de documento."""
        self.metrics.total_views += 1
        
        # Atualiza documentos populares
        popular_docs = {doc['id']: doc['views'] for doc in self.metrics.popular_documents}
        popular_docs[document_id] = popular_docs.get(document_id, 0) + 1
        
        # Mantém top 10
        sorted_docs = sorted(popular_docs.items(), key=lambda x: x[1], reverse=True)[:10]
        self.metrics.popular_documents = [
            {'id': doc_id, 'views': views, 'title': self.documents.get(doc_id, {}).title if doc_id in self.documents else 'Unknown'}
            for doc_id, views in sorted_docs
        ]
    
    async def record_feedback(self, document_id: str, rating: int, comment: str = ""):
        """Registra feedback de documento."""
        if document_id in self.documents:
            # Atualiza métricas de feedback
            if 'ratings' not in self.metrics.user_feedback:
                self.metrics.user_feedback['ratings'] = []
            
            self.metrics.user_feedback['ratings'].append({
                'document_id': document_id,
                'rating': rating,
                'comment': comment,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Calcula média
            ratings = [r['rating'] for r in self.metrics.user_feedback['ratings']]
            self.metrics.avg_rating = sum(ratings) / len(ratings)


# Instância global
documentation_manager: Optional[DocumentationManager] = None


def get_documentation_manager() -> DocumentationManager:
    """Obtém instância global do documentation manager."""
    global documentation_manager
    if documentation_manager is None:
        config = DocumentationConfig()
        documentation_manager = DocumentationManager(config)
    
    return documentation_manager