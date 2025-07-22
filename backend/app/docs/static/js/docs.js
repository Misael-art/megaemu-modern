// Documentation JavaScript

// Global variables
let currentTheme = localStorage.getItem('theme') || 'light';
let currentLanguage = localStorage.getItem('language') || 'pt';

// Initialize documentation features
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeLanguage();
    initializeSearch();
    initializeNavigation();
    initializeCodeCopy();
    initializeFeedback();
    initializeAnalytics();
    initializeAccessibility();
});

// Theme Management
function initializeTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;
    
    // Apply saved theme
    body.setAttribute('data-theme', currentTheme);
    updateThemeIcon();
    
    // Theme toggle event
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            body.setAttribute('data-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
            updateThemeIcon();
            
            // Track theme change
            trackEvent('Documentation', 'theme_toggle', currentTheme);
        });
    }
}

function updateThemeIcon() {
    const themeIcon = document.querySelector('#themeToggle i');
    if (themeIcon) {
        themeIcon.className = currentTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

// Language Management
function initializeLanguage() {
    const languageSelector = document.getElementById('languageSelector');
    
    // Set current language
    if (languageSelector) {
        languageSelector.value = currentLanguage;
        
        languageSelector.addEventListener('change', function() {
            currentLanguage = this.value;
            localStorage.setItem('language', currentLanguage);
            
            // Track language change
            trackEvent('Documentation', 'language_change', currentLanguage);
            
            // Reload page with new language (in real implementation)
            // window.location.reload();
        });
    }
}

// Search Functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('input[type="search"]');
    
    searchInputs.forEach(input => {
        const resultsContainer = input.parentElement.parentElement.querySelector('.search-results');
        if (!resultsContainer) return;
        
        let searchTimeout;
        
        input.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            if (query.length < 2) {
                hideSearchResults(resultsContainer);
                return;
            }
            
            searchTimeout = setTimeout(() => {
                performSearch(query, resultsContainer);
            }, 300);
        });
        
        input.addEventListener('focus', function() {
            if (this.value.trim().length >= 2) {
                resultsContainer.style.display = 'block';
            }
        });
        
        // Hide results when clicking outside
        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !resultsContainer.contains(e.target)) {
                hideSearchResults(resultsContainer);
            }
        });
        
        // Keyboard navigation
        input.addEventListener('keydown', function(e) {
            handleSearchKeyboard(e, resultsContainer);
        });
    });
}

function performSearch(query, resultsContainer) {
    // Show loading state
    resultsContainer.innerHTML = '<div class="search-loading"><i class="fas fa-spinner fa-spin"></i> Buscando...</div>';
    resultsContainer.style.display = 'block';
    
    // Simulate API call (replace with actual search API)
    setTimeout(() => {
        const results = mockSearch(query);
        displaySearchResults(results, resultsContainer, query);
    }, 500);
    
    // Track search
    trackEvent('Documentation', 'search', query);
}

function mockSearch(query) {
    // Mock search results - replace with actual API call
    const mockData = [
        {
            id: 'getting-started',
            title: 'Guia de Início Rápido',
            excerpt: 'Aprenda a configurar e usar o MegaEmu Modern em poucos minutos. Este guia cobre instalação, configuração básica e primeiros passos.',
            url: '/getting-started.html',
            type: 'guide',
            tags: ['iniciante', 'configuração', 'instalação']
        },
        {
            id: 'api-reference',
            title: 'API Reference',
            excerpt: 'Documentação completa da API REST com exemplos de código e especificações detalhadas para todos os endpoints.',
            url: '/api-reference.html',
            type: 'api_reference',
            tags: ['api', 'rest', 'endpoints']
        },
        {
            id: 'rom-import',
            title: 'Como Importar ROMs',
            excerpt: 'Tutorial passo-a-passo para importar seus ROMs favoritos, incluindo formatos suportados e resolução de problemas.',
            url: '/rom-import-tutorial.html',
            type: 'tutorial',
            tags: ['roms', 'importação', 'tutorial']
        },
        {
            id: 'troubleshooting',
            title: 'Troubleshooting',
            excerpt: 'Soluções para problemas comuns, guias de resolução de erros e dicas de otimização de performance.',
            url: '/troubleshooting-guide.html',
            type: 'troubleshooting',
            tags: ['problemas', 'erros', 'soluções']
        },
        {
            id: 'configuration',
            title: 'Guia de Configuração',
            excerpt: 'Configurações avançadas do sistema, personalização da interface e otimização de performance.',
            url: '/configuration-guide.html',
            type: 'guide',
            tags: ['configuração', 'personalização', 'avançado']
        }
    ];
    
    return mockData.filter(item => 
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.excerpt.toLowerCase().includes(query.toLowerCase()) ||
        item.tags.some(tag => tag.toLowerCase().includes(query.toLowerCase()))
    );
}

function displaySearchResults(results, container, query) {
    if (results.length === 0) {
        container.innerHTML = `
            <div class="search-no-results">
                <i class="fas fa-search"></i>
                <p>Nenhum resultado encontrado para "${query}"</p>
                <small>Tente usar termos diferentes ou verifique a ortografia</small>
            </div>
        `;
        return;
    }
    
    const html = results.map((result, index) => `
        <div class="search-result-item" data-index="${index}">
            <a href="${result.url}" class="search-result-link">
                <div class="search-result-title">${highlightText(result.title, query)}</div>
                <div class="search-result-excerpt">${highlightText(result.excerpt, query)}</div>
                <div class="search-result-type">
                    <i class="fas fa-${getTypeIcon(result.type)}"></i>
                    ${getTypeLabel(result.type)}
                </div>
            </a>
        </div>
    `).join('');
    
    container.innerHTML = html;
    
    // Add click tracking to results
    container.querySelectorAll('.search-result-link').forEach((link, index) => {
        link.addEventListener('click', function() {
            trackEvent('Documentation', 'search_result_click', `${query}:${results[index].id}`);
        });
    });
}

function highlightText(text, query) {
    const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function getTypeIcon(type) {
    const icons = {
        'api_reference': 'code',
        'tutorial': 'book',
        'guide': 'file-alt',
        'troubleshooting': 'exclamation-triangle',
        'faq': 'question-circle',
        'examples': 'code-branch'
    };
    return icons[type] || 'file';
}

function getTypeLabel(type) {
    const labels = {
        'api_reference': 'API Reference',
        'tutorial': 'Tutorial',
        'guide': 'Guia',
        'troubleshooting': 'Troubleshooting',
        'faq': 'FAQ',
        'examples': 'Exemplos'
    };
    return labels[type] || type;
}

function hideSearchResults(container) {
    container.style.display = 'none';
}

function handleSearchKeyboard(e, resultsContainer) {
    const results = resultsContainer.querySelectorAll('.search-result-item');
    if (results.length === 0) return;
    
    const currentActive = resultsContainer.querySelector('.search-result-item.active');
    let activeIndex = currentActive ? parseInt(currentActive.dataset.index) : -1;
    
    switch (e.key) {
        case 'ArrowDown':
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, results.length - 1);
            updateActiveResult(results, activeIndex);
            break;
        case 'ArrowUp':
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            updateActiveResult(results, activeIndex);
            break;
        case 'Enter':
            e.preventDefault();
            if (currentActive) {
                const link = currentActive.querySelector('.search-result-link');
                if (link) link.click();
            }
            break;
        case 'Escape':
            hideSearchResults(resultsContainer);
            break;
    }
}

function updateActiveResult(results, activeIndex) {
    results.forEach((result, index) => {
        result.classList.toggle('active', index === activeIndex);
    });
}

// Navigation Enhancement
function initializeNavigation() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', function(e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Active navigation highlighting
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const currentPath = window.location.pathname;
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
    
    // Mobile menu auto-close
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        document.addEventListener('click', function(e) {
            if (!navbarCollapse.contains(e.target) && !navbarToggler.contains(e.target)) {
                const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse);
                if (bsCollapse && navbarCollapse.classList.contains('show')) {
                    bsCollapse.hide();
                }
            }
        });
    }
}

// Code Copy Functionality
function initializeCodeCopy() {
    document.querySelectorAll('pre[class*="language-"]').forEach(pre => {
        const button = document.createElement('button');
        button.className = 'copy-code-btn';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copiar código';
        
        button.addEventListener('click', function() {
            const code = pre.querySelector('code');
            if (code) {
                copyToClipboard(code.textContent);
                showCopyFeedback(button);
                trackEvent('Documentation', 'code_copy', 'success');
            }
        });
        
        pre.style.position = 'relative';
        pre.appendChild(button);
    });
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
    }
}

function showCopyFeedback(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '<i class="fas fa-check"></i>';
    button.classList.add('copied');
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.classList.remove('copied');
    }, 2000);
}

// Feedback System
function initializeFeedback() {
    const feedbackForms = document.querySelectorAll('.feedback-form');
    
    feedbackForms.forEach(form => {
        const stars = form.querySelectorAll('.star-rating .star');
        const submitBtn = form.querySelector('.feedback-submit');
        const textarea = form.querySelector('.feedback-text');
        let selectedRating = 0;
        
        // Star rating
        stars.forEach((star, index) => {
            star.addEventListener('click', function() {
                selectedRating = index + 1;
                updateStarRating(stars, selectedRating);
                
                if (submitBtn) {
                    submitBtn.disabled = false;
                }
            });
            
            star.addEventListener('mouseenter', function() {
                updateStarRating(stars, index + 1, true);
            });
        });
        
        form.addEventListener('mouseleave', function() {
            updateStarRating(stars, selectedRating);
        });
        
        // Submit feedback
        if (submitBtn) {
            submitBtn.addEventListener('click', function() {
                const feedback = {
                    rating: selectedRating,
                    text: textarea ? textarea.value : '',
                    page: window.location.pathname,
                    timestamp: new Date().toISOString()
                };
                
                submitFeedback(feedback);
                showFeedbackSuccess(form);
                trackEvent('Documentation', 'feedback_submit', `rating:${selectedRating}`);
            });
        }
    });
}

function updateStarRating(stars, rating, hover = false) {
    stars.forEach((star, index) => {
        star.classList.toggle('active', index < rating);
        star.classList.toggle('hover', hover && index < rating);
    });
}

function submitFeedback(feedback) {
    // In real implementation, send to API
    console.log('Feedback submitted:', feedback);
    
    // Store locally for now
    const existingFeedback = JSON.parse(localStorage.getItem('documentation_feedback') || '[]');
    existingFeedback.push(feedback);
    localStorage.setItem('documentation_feedback', JSON.stringify(existingFeedback));
}

function showFeedbackSuccess(form) {
    const successMessage = document.createElement('div');
    successMessage.className = 'feedback-success';
    successMessage.innerHTML = `
        <i class="fas fa-check-circle"></i>
        <span>Obrigado pelo seu feedback!</span>
    `;
    
    form.appendChild(successMessage);
    
    setTimeout(() => {
        successMessage.remove();
    }, 3000);
}

// Analytics Integration
function initializeAnalytics() {
    // Track page view
    trackEvent('Documentation', 'page_view', window.location.pathname);
    
    // Track scroll depth
    let maxScroll = 0;
    window.addEventListener('scroll', throttle(() => {
        const scrollPercent = Math.round((window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100);
        if (scrollPercent > maxScroll) {
            maxScroll = scrollPercent;
            if (maxScroll % 25 === 0) { // Track at 25%, 50%, 75%, 100%
                trackEvent('Documentation', 'scroll_depth', `${maxScroll}%`);
            }
        }
    }, 1000));
    
    // Track time on page
    const startTime = Date.now();
    window.addEventListener('beforeunload', () => {
        const timeOnPage = Math.round((Date.now() - startTime) / 1000);
        trackEvent('Documentation', 'time_on_page', timeOnPage);
    });
}

function trackEvent(category, action, label) {
    // Google Analytics 4
    if (typeof gtag !== 'undefined') {
        gtag('event', action, {
            event_category: category,
            event_label: label
        });
    }
    
    // Custom analytics
    if (typeof customAnalytics !== 'undefined') {
        customAnalytics.track(category, action, label);
    }
    
    // Console log for development
    if (window.location.hostname === 'localhost') {
        console.log('Analytics Event:', { category, action, label });
    }
}

// Accessibility Features
function initializeAccessibility() {
    // Skip to content link
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link sr-only';
    skipLink.textContent = 'Pular para o conteúdo principal';
    document.body.insertBefore(skipLink, document.body.firstChild);
    
    skipLink.addEventListener('focus', function() {
        this.classList.remove('sr-only');
    });
    
    skipLink.addEventListener('blur', function() {
        this.classList.add('sr-only');
    });
    
    // Keyboard navigation for custom elements
    document.querySelectorAll('.filter-tag, .view-toggle button').forEach(element => {
        if (!element.hasAttribute('tabindex')) {
            element.setAttribute('tabindex', '0');
        }
        
        element.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });
    
    // ARIA labels for dynamic content
    document.querySelectorAll('.search-results').forEach(container => {
        container.setAttribute('role', 'listbox');
        container.setAttribute('aria-label', 'Resultados da busca');
    });
    
    // Focus management for modals and dropdowns
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Close any open search results
            document.querySelectorAll('.search-results').forEach(container => {
                hideSearchResults(container);
            });
        }
    });
}

// Utility Functions
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

function debounce(func, wait, immediate) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

// Export functions for external use
window.DocsJS = {
    trackEvent,
    performSearch,
    copyToClipboard,
    updateTheme: function(theme) {
        currentTheme = theme;
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateThemeIcon();
    },
    updateLanguage: function(language) {
        currentLanguage = language;
        localStorage.setItem('language', language);
    }
};