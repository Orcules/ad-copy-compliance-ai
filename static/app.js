// Global variables
let currentArticleData = null; // Legacy - for single article
let currentArticlesData = []; // NEW - for multiple articles
let availableTemplates = [];
let generatedHeadlines = [];
let generatedHeadlinesByArticle = {}; // NEW - headlines organized by article
let availableCountries = [];
let countryLanguageMap = {};
let currentArticleFilter = 'all'; // NEW - for filtering results by article
let maxInputs = 10; // Maximum number of URL/text inputs allowed
let availableLanguages = [];

// DOM elements (will be initialized after DOM loads)
let articleUrlInput;
let analyzeBtn;
const articlePreview = document.getElementById('articlePreview');
const templatesSection = document.getElementById('templatesSection');
const templatesContainer = document.getElementById('templatesContainer');
const variantsSection = document.getElementById('variantsSection');
const generateSection = document.getElementById('generateSection');
const headlineForm = document.getElementById('headlineForm');
const resultsSection = document.getElementById('resultsSection');
const headlinesContainer = document.getElementById('headlinesContainer');
const loadingOverlay = document.getElementById('loadingOverlay');
const errorModal = document.getElementById('errorModal');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Application initializing...');
    
    // Initialize DOM elements after DOM is ready
    articleUrlInput = document.getElementById('articleUrl');
    analyzeBtn = document.getElementById('analyzeAllUrlsBtn'); // Updated ID
    console.log('🔧 DOM elements initialized:', {articleUrlInput, analyzeBtn});
    
    // Initialize everything in sequence
    setTimeout(async () => {
        try {
            loadTemplates();
            await loadCountries();
            await populateAllLanguages();
            setupEventListeners();
            initializeInputs();
            clearStorage();
            console.log('✅ Application initialized');
        } catch (error) {
            console.error('❌ Error during initialization:', error);
        }
    }, 100);
});

// Setup event listeners
function setupEventListeners() {
    console.log('🔗 Setting up event listeners...');
    
    try {
        console.log('analyzeBtn element:', analyzeBtn);
        
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', function(e) {
                console.log('🔍 Analyze button clicked!');
                e.preventDefault();
                analyzeArticle();
            });
            console.log('✅ analyzeBtn event listener added');
        } else {
            console.error('❌ analyzeBtn element not found!');
        }
        
        const analyzeTextBtn = document.getElementById('analyzeAllTextsBtn'); // Updated ID
        console.log('analyzeTextBtn element:', analyzeTextBtn);
        
        if (analyzeTextBtn) {
            analyzeTextBtn.addEventListener('click', function(e) {
                console.log('📝 Analyze Text button clicked!');
                e.preventDefault();
                console.log('📝 Calling analyzeText()...');
                analyzeText();
            });
            console.log('✅ analyzeTextBtn event listener added successfully');
        } else {
            console.error('❌ analyzeTextBtn element not found in DOM!');
            console.log('📝 Will try to add listener after delay...');
            setTimeout(() => {
                const retryBtn = document.getElementById('analyzeTextBtn');
                console.log('📝 Retry - analyzeTextBtn element:', retryBtn);
                if (retryBtn) {
                    retryBtn.addEventListener('click', function(e) {
                        console.log('📝 Analyze Text button clicked (retry)!');
                        e.preventDefault();
                        analyzeText();
                    });
                    console.log('✅ analyzeTextBtn event listener added (retry successful)');
                } else {
                    console.error('❌ analyzeTextBtn still not found after retry!');
                }
            }, 1000);
        }
    } catch (error) {
        console.error('❌ Error setting up analyze button listeners:', error);
        console.error('Error details:', error.message);
        console.error('Error stack:', error.stack);
    }
    headlineForm.addEventListener('submit', generateHeadlines);
    document.getElementById('exportJsonBtn').addEventListener('click', () => exportResults('json'));
    document.getElementById('exportCsvBtn').addEventListener('click', () => exportResults('csv'));
    document.getElementById('copyAllBtn').addEventListener('click', copyAllHeadlines);
    document.getElementById('selectAllBtn').addEventListener('click', toggleSelectAll);
    document.getElementById('copySelectedBtn').addEventListener('click', copySelectedHeadlines);
    
    // Toggle between URL and Text mode
    document.getElementById('urlModeBtn').addEventListener('click', () => switchInputMode('url'));
    document.getElementById('textModeBtn').addEventListener('click', () => switchInputMode('text'));
    
    // Add listeners for calculation updates
    document.getElementById('nVariants').addEventListener('input', updateTotalCalculation);
    document.addEventListener('change', function(e) {
        if (e.target.name === 'template') {
            updateTotalCalculation();
        }
    });
    
    // Add listener for country selection
    document.getElementById('countryOverride').addEventListener('change', onCountryChange);
    
    // Add listeners for dropdown search - delay to ensure dropdowns are populated
    setTimeout(() => {
        setupDropdownSearch('countrySearch', 'countryOverride');
        setupDropdownSearch('languageSearch', 'languageOverride');
    }, 500);
    
    // Add listener for refresh templates button
    document.getElementById('refreshTemplatesBtn').addEventListener('click', refreshTemplates);
    
    // Add listener for template search
    document.getElementById('templateSearch').addEventListener('input', filterTemplates);
    
    // Add listener for select all templates
    document.getElementById('selectAllTemplatesBtn').addEventListener('click', toggleSelectAllTemplates);
}

// Switch between URL and Text input modes
function switchInputMode(mode) {
    const urlSection = document.getElementById('urlInputSection');
    const textSection = document.getElementById('textInputSection');
    const urlModeBtn = document.getElementById('urlModeBtn');
    const textModeBtn = document.getElementById('textModeBtn');
    
    if (mode === 'url') {
        urlSection.style.display = 'block';
        textSection.style.display = 'none';
        urlModeBtn.classList.add('active');
        textModeBtn.classList.remove('active');
    } else {
        urlSection.style.display = 'none';
        textSection.style.display = 'block';
        urlModeBtn.classList.remove('active');
        textModeBtn.classList.add('active');
    }
}

// Load templates from the server
async function loadTemplates() {
    try {
        console.log('Loading templates from /api/templates...');
        const response = await fetch('/api/templates');
        console.log('Templates response status:', response.status);
        
        const data = await response.json();
        console.log('Templates response data:', data);
        
        if (data.ok) {
            availableTemplates = data.templates;
            console.log('Successfully loaded templates:', availableTemplates.length, 'templates');
            console.log('Template names:', availableTemplates.map(t => t.name));
        } else {
            console.error('Templates API returned error:', data.error);
            showError('Failed to load templates: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading templates:', error);
        showError('Failed to load templates. Please refresh the page.');
    }
}

// Analyze article from URL
async function analyzeArticle() {
    console.log('🔍 analyzeArticle function called');
    const url = articleUrlInput.value.trim();
    console.log('URL value:', url);
    if (!url) {
        console.log('❌ No URL provided');
        showError('Please enter an article URL');
        return;
    }

    setAnalyzeLoading(true);
    
    try {
        const response = await fetch('/api/scrape-article', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.ok) {
            currentArticleData = data.article;
            displayArticlePreview(data.article);
            displayTemplates();
            showNextSections();
        } else {
            showError('Failed to analyze article: ' + data.error);
        }
    } catch (error) {
        console.error('Error analyzing article:', error);
        showError('Failed to analyze article. Please check the URL and try again.');
    } finally {
        setAnalyzeLoading(false);
    }
}

// Analyze free text
async function analyzeText() {
    console.log('📝 analyzeText function called');
    const textArea = document.getElementById('freeText');
    console.log('📝 Text area element:', textArea);
    
    if (!textArea) {
        console.error('❌ freeText textarea not found!');
        showError('System error: Text input field not found');
        return;
    }
    
    const text = textArea.value.trim();
    console.log('📝 Text length:', text.length);
    console.log('📝 First 100 chars:', text.substring(0, 100));
    
    if (!text) {
        console.log('❌ No text provided');
        showError('Please enter article content');
        return;
    }
    
    if (text.length < 100) {
        console.log('❌ Text too short:', text.length, 'characters');
        showError('Article content is too short. Please enter at least 100 characters.');
        return;
    }

    const analyzeTextBtn = document.getElementById('analyzeTextBtn');
    console.log('📝 Analyze button:', analyzeTextBtn);
    
    if (!analyzeTextBtn) {
        console.error('❌ analyzeTextBtn not found!');
        showError('System error: Analyze button not found');
        return;
    }
    
    const btnText = analyzeTextBtn.querySelector('.btn-text');
    const btnLoading = analyzeTextBtn.querySelector('.btn-loading');
    
    console.log('📝 Setting button to loading state...');
    btnText.style.display = 'none';
    btnLoading.style.display = 'flex';
    analyzeTextBtn.disabled = true;
    
    try {
        console.log('📝 Sending request to /api/scrape-article...');
        const response = await fetch('/api/scrape-article', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });
        
        console.log('📝 Response status:', response.status);
        const data = await response.json();
        console.log('📝 Response data:', data);
        
        if (data.ok) {
            console.log('✅ Text analysis successful!');
            currentArticleData = data.article;
            console.log('📝 Article data:', currentArticleData);
            displayArticlePreview(data.article);
            displayTemplates();
            showNextSections();
        } else {
            console.error('❌ Server returned error:', data.error);
            showError('Failed to analyze text: ' + data.error);
        }
    } catch (error) {
        console.error('❌ Error analyzing text:', error);
        console.error('Error details:', error.message);
        console.error('Error stack:', error.stack);
        showError('Failed to analyze text. Please try again. Error: ' + error.message);
    } finally {
        console.log('📝 Resetting button state...');
        btnText.style.display = 'block';
        btnLoading.style.display = 'none';
        analyzeTextBtn.disabled = false;
    }
}

// Display article preview
function displayArticlePreview(article) {
    document.getElementById('articleTitle').textContent = article.title;
    document.getElementById('articleLanguage').textContent = article.language + ' (' + article.language_code + ')';
    
    // Show detected country if available
    if (article.detected_country) {
        document.getElementById('detectedCountry').textContent = article.detected_country;
        document.getElementById('detectedCountryItem').style.display = 'block';
        
        // Auto-select the detected country in the dropdown using GEO code
        const countrySelect = document.getElementById('countryOverride');
        const detectedGeo = article.detected_country_geo;
        if (detectedGeo) {
            for (let option of countrySelect.options) {
                if (option.value === detectedGeo) {
                    countrySelect.value = detectedGeo;
                    // Trigger country change to update languages
                    onCountryChange();
                    break;
                }
            }
        }
    } else {
        document.getElementById('detectedCountryItem').style.display = 'none';
    }
    
    const contentPreview = article.content.substring(0, 300) + (article.content.length > 300 ? '...' : '');
    document.getElementById('articleContent').textContent = contentPreview;
    
    // Setup read more button
    const readMoreBtn = document.getElementById('readMoreBtn');
    if (article.content.length > 300) {
        readMoreBtn.style.display = 'block';
        let isExpanded = false;
        
        readMoreBtn.onclick = function() {
            isExpanded = !isExpanded;
            const contentDiv = document.getElementById('articleContent');
            const readMoreText = readMoreBtn.querySelector('.read-more-text');
            const readLessText = readMoreBtn.querySelector('.read-less-text');
            
            if (isExpanded) {
                contentDiv.textContent = article.content;
                readMoreText.style.display = 'none';
                readLessText.style.display = 'inline';
            } else {
                contentDiv.textContent = article.content.substring(0, 300) + '...';
                readMoreText.style.display = 'inline';
                readLessText.style.display = 'none';
            }
        };
    } else {
        readMoreBtn.style.display = 'none';
    }
    
    articlePreview.style.display = 'block';
}

// Display available templates
function displayTemplates() {
    console.log('displayTemplates called with', availableTemplates.length, 'templates');
    console.log('templatesContainer element:', templatesContainer);
    
    if (!templatesContainer) {
        console.error('templatesContainer element not found!');
        return;
    }
    
    if (availableTemplates.length === 0) {
        console.warn('No templates available to display');
        templatesContainer.innerHTML = '<p>No templates available. Please check the connection.</p>';
        updateTemplateCount(0);
        return;
    }
    
    // Store all templates for filtering
    window.allTemplates = availableTemplates;
    
    // Update template count
    updateTemplateCount(availableTemplates.length);
    
    templatesContainer.innerHTML = '';
    
    availableTemplates.forEach((template, index) => {
        console.log(`Creating template ${index}:`, template);
        const templateItem = document.createElement('div');
        templateItem.className = 'template-item';
        templateItem.innerHTML = `
            <label class="template-checkbox">
                <input type="checkbox" name="template" value="${template.id}" data-name="${template.name}">
                <span class="checkmark"></span>
                <div class="template-info">
                    <div class="template-name">${template.name}</div>
                    <div class="template-description">${template.description}</div>
                </div>
            </label>
        `;
        templatesContainer.appendChild(templateItem);
    });
    
    console.log('Templates displayed successfully');
}

// Show next sections after article analysis
function showNextSections() {
    // Store all templates for filtering
    window.allTemplates = availableTemplates;
    
    // Update template count
    updateTemplateCount(availableTemplates.length);
    
    templatesSection.style.display = 'block';
    variantsSection.style.display = 'block';
    generateSection.style.display = 'block';
}

// Generate headlines
async function generateHeadlines(event) {
    event.preventDefault();
    
    const selectedTemplates = Array.from(document.querySelectorAll('input[name="template"]:checked'))
        .map(cb => cb.value);
    
    if (selectedTemplates.length === 0) {
        showError('Please select at least one template');
        return;
    }
    
    const nVariants = parseInt(document.getElementById('nVariants').value);
    
    // Check if we have articles (either single or multiple)
    const hasArticles = currentArticlesData.length > 0 || currentArticleData;
    if (!hasArticles) {
        showError('Please analyze an article first');
        return;
    }
    
    setGenerateLoading(true);
    
    // Handle multiple articles
    if (currentArticlesData.length > 0) {
        showLoadingOverlay(`Generating headlines for ${currentArticlesData.length} article(s)...`);
        await generateHeadlinesForMultipleArticles(selectedTemplates, nVariants);
    } 
    // Handle single article (legacy)
    else if (currentArticleData) {
        showLoadingOverlay('Generating headlines...');
        await generateHeadlinesForSingleArticle(selectedTemplates, nVariants);
    }
    
    setGenerateLoading(false);
    hideLoadingOverlay();
}

// Generate headlines for multiple articles
async function generateHeadlinesForMultipleArticles(selectedTemplates, nVariants) {
    try {
        generatedHeadlines = [];
        generatedHeadlinesByArticle = {};
        // Start with first article
        currentArticleFilter = currentArticlesData[0];
        
        for (let i = 0; i < currentArticlesData.length; i++) {
            const article = currentArticlesData[i];
            showLoadingOverlay(`Generating headlines for article ${i + 1}/${currentArticlesData.length}...`);
            
            // Create a copy of article data to potentially modify with overrides
            let articleDataToSend = { ...article };
            
            // Check if there are language/country overrides for this specific article input
            const inputIndex = article.inputIndex; // This is now the actual input ID, e.g., "urlInput_0" or "textInput_0"
            if (inputIndex !== undefined) {
                // Try to find override selects for this input using actual ID
                const langOverrideSelect = document.getElementById(`lang_${inputIndex}`);
                const countryOverrideSelect = document.getElementById(`country_${inputIndex}`);
                
                console.log(`Looking for overrides: lang_${inputIndex}=${langOverrideSelect?.value}, country_${inputIndex}=${countryOverrideSelect?.value}`);
                
                if (langOverrideSelect && langOverrideSelect.value) {
                    const langCode = langOverrideSelect.value;
                    articleDataToSend.language_code = langCode;
                    articleDataToSend.language = getLanguageNameFromCode(langCode);
                    console.log(`Applied language override for article ${i + 1}: ${langCode}`);
                }
                
                if (countryOverrideSelect && countryOverrideSelect.value) {
                    const countryGeo = countryOverrideSelect.value;
                    articleDataToSend.detected_country_geo = countryGeo;
                    const countryData = availableCountries.find(c => c.geo === countryGeo);
                    if (countryData) {
                        articleDataToSend.detected_country = countryData.name;
                    }
                    console.log(`Applied country override for article ${i + 1}: ${countryGeo}`);
                }
            }
            
            const response = await fetch('/api/generate-headlines', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    article_data: articleDataToSend,
                    template_ids: selectedTemplates,
                    n_variants: nVariants,
                    language_override: articleDataToSend.language_code
                })
            });
            
            const data = await response.json();
            
            if (data.ok) {
                // Mark headlines with article index
                const headlinesWithArticle = data.headlines.map(h => ({
                    ...h,
                    articleIndex: i,
                    articleTitle: article.title
                }));
                
                generatedHeadlines.push(...headlinesWithArticle);
                generatedHeadlinesByArticle[i] = headlinesWithArticle;
            } else {
                showToast(`Failed for article ${i + 1}: ${data.error}`, 'error');
            }
        }
        
        if (generatedHeadlines.length > 0) {
            displayResults({
                headlines: generatedHeadlines,
                total_headlines: generatedHeadlines.length,
                templates_used: [...new Set(generatedHeadlines.map(h => h.template))],
                article_language: currentArticlesData[0]?.language || 'Multiple'
            });
            showToast(`Successfully generated ${generatedHeadlines.length} headlines!`);
        } else {
            showError('Failed to generate any headlines');
        }
    } catch (error) {
        console.error('Error generating headlines:', error);
        showError('Failed to generate headlines. Please try again.');
    }
}

// Generate headlines for single article (legacy)
async function generateHeadlinesForSingleArticle(selectedTemplates, nVariants) {
    try {
        // Check for language override
        const languageOverride = document.getElementById('languageOverride')?.value;
        let articleDataToSend = { ...currentArticleData };
        
        if (languageOverride) {
            articleDataToSend.language_code = languageOverride;
            articleDataToSend.language = getLanguageNameFromCode(languageOverride);
        }
        
        const response = await fetch('/api/generate-headlines', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                article_data: articleDataToSend,
                template_ids: selectedTemplates,
                n_variants: nVariants,
                language_override: languageOverride
            })
        });
        
        const data = await response.json();
        
        if (data.ok) {
            generatedHeadlines = data.headlines;
            displayResults(data);
        } else {
            showError('Failed to generate headlines: ' + data.error);
        }
    } catch (error) {
        console.error('Error generating headlines:', error);
        showError('Failed to generate headlines. Please try again.');
    }
}

// Display results
function displayResults(data) {
    // Update stats
    document.getElementById('totalHeadlines').textContent = data.total_headlines;
    document.getElementById('templatesUsed').textContent = data.templates_used.join(', ');
    document.getElementById('resultsLanguage').textContent = data.article_language;
    
    // Group headlines by template
    const headlinesByTemplate = {};
    data.headlines.forEach(headline => {
        if (!headlinesByTemplate[headline.template]) {
            headlinesByTemplate[headline.template] = [];
        }
        headlinesByTemplate[headline.template].push(headline);
    });
    
    // Display headlines
    headlinesContainer.innerHTML = '';
    
    Object.keys(headlinesByTemplate).forEach(templateName => {
        const templateSection = document.createElement('div');
        templateSection.className = 'template-results';
        
        // Find the template description
        const template = availableTemplates.find(t => t.name === templateName);
        const templateDescription = template ? template.description : '';
        
        const templateHeader = document.createElement('div');
        templateHeader.className = 'template-header';
        templateHeader.innerHTML = `
            <div class="template-title-section">
                <h3>${templateName}</h3>
                ${templateDescription ? `<p class="template-description-results">${templateDescription}</p>` : ''}
            </div>
            <span class="headline-count">${headlinesByTemplate[templateName].length} headlines</span>
        `;
        
        const headlinesList = document.createElement('div');
        headlinesList.className = 'headlines-list';
        
        headlinesByTemplate[templateName].forEach((headline, index) => {
            const headlineItem = document.createElement('div');
            headlineItem.className = 'headline-item';
            
            // Check for compliance issues
            const hasIssues = headline.compliance?.flagged || headline.moderation?.flagged;
            const issueClass = hasIssues ? 'has-issues' : '';
            
            // Create unique ID for this headline
            const headlineId = `headline_${templateName.replace(/\s+/g, '_')}_${index}`;
            
            headlineItem.innerHTML = `
                <div class="headline-checkbox-wrapper">
                    <input type="checkbox" class="headline-checkbox" id="${headlineId}" data-headline="${headline.headline.replace(/"/g, '&quot;')}">
                    <label for="${headlineId}" class="headline-content ${issueClass}">
                        <div class="headline-text">${headline.headline}</div>
                        <div class="headline-meta">
                            <span class="char-count">${headline.character_count} chars</span>
                            ${hasIssues ? '<span class="issue-badge">Issues Found</span>' : ''}
                            <button class="copy-btn-small" onclick="event.preventDefault(); copyHeadline('${headline.headline.replace(/'/g, "\\'")}')">Copy</button>
                        </div>
                    </label>
                </div>
                ${hasIssues ? createIssuesDisplay(headline) : ''}
            `;
            
            headlinesList.appendChild(headlineItem);
        });
        
        templateSection.appendChild(templateHeader);
        templateSection.appendChild(headlinesList);
        headlinesContainer.appendChild(templateSection);
    });
    
    resultsSection.style.display = 'block';
    
    // Update navigation UI if we have multiple articles
    if (currentArticlesData.length > 1) {
        updateNavigationUI();
    }
    
    resultsSection.scrollIntoView({ behavior: 'smooth' });
    
    // Add event listeners to checkboxes for updating selected count
    document.querySelectorAll('.headline-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedCount);
    });
    
    // Reset selected count
    updateSelectedCount();
}

// Update selected count
function updateSelectedCount() {
    const selectedCheckboxes = document.querySelectorAll('.headline-checkbox:checked');
    const count = selectedCheckboxes.length;
    document.getElementById('selectedCount').textContent = count;
    
    // Enable/disable copy selected button
    const copySelectedBtn = document.getElementById('copySelectedBtn');
    if (count > 0) {
        copySelectedBtn.disabled = false;
    } else {
        copySelectedBtn.disabled = true;
    }
}

// Toggle select all/deselect all
function toggleSelectAll() {
    const selectAllBtn = document.getElementById('selectAllBtn');
    const checkboxes = document.querySelectorAll('.headline-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = !allChecked;
    });
    
    // Update button text
    if (allChecked) {
        selectAllBtn.textContent = 'Select All';
    } else {
        selectAllBtn.textContent = 'Deselect All';
    }
    
    updateSelectedCount();
}

// Copy selected headlines
function copySelectedHeadlines() {
    const selectedCheckboxes = document.querySelectorAll('.headline-checkbox:checked');
    
    if (selectedCheckboxes.length === 0) {
        showToast('No headlines selected', 'error');
        return;
    }
    
    const selectedHeadlines = Array.from(selectedCheckboxes).map(cb => cb.dataset.headline);
    const headlinesText = selectedHeadlines.join('\n');
    
    navigator.clipboard.writeText(headlinesText).then(() => {
        showToast(`${selectedCheckboxes.length} headlines copied to clipboard!`);
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast('Failed to copy headlines', 'error');
    });
}

// Create issues display
function createIssuesDisplay(headline) {
    let issuesHtml = '<div class="issues-display">';
    
    if (headline.moderation?.flagged) {
        issuesHtml += '<div class="issue-item moderation">⚠️ Content Moderation: Flagged content detected</div>';
    }
    
    if (headline.compliance?.flagged) {
        const issues = headline.compliance.issues || [];
        issues.forEach(issue => {
            issuesHtml += `<div class="issue-item compliance">🚫 ${issue}</div>`;
        });
    }
    
    issuesHtml += '</div>';
    return issuesHtml;
}

// Copy single headline
function copyHeadline(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Headline copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast('Failed to copy headline', 'error');
    });
}

// Copy all headlines
function copyAllHeadlines() {
    const allHeadlines = generatedHeadlines.map(h => h.headline).join('\n');
    navigator.clipboard.writeText(allHeadlines).then(() => {
        showToast('All headlines copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast('Failed to copy headlines', 'error');
    });
}

// Export results
function exportResults(format) {
    if (generatedHeadlines.length === 0) {
        showError('No headlines to export');
        return;
    }
    
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `headlines_${timestamp}`;
    
    if (format === 'json') {
        const data = {
            article: currentArticleData,
            headlines: generatedHeadlines,
            exported_at: new Date().toISOString()
        };
        downloadFile(JSON.stringify(data, null, 2), `${filename}.json`, 'application/json');
    } else if (format === 'csv') {
        const csvContent = generateCSV(generatedHeadlines);
        downloadFile(csvContent, `${filename}.csv`, 'text/csv');
    }
}

// Generate CSV content
function generateCSV(headlines) {
    const headers = ['Template', 'Headline', 'Character Count', 'Language', 'Has Issues', 'Issues'];
    const rows = headlines.map(h => [
        h.template,
        `"${h.headline.replace(/"/g, '""')}"`,
        h.character_count,
        h.language_code,
        (h.compliance?.flagged || h.moderation?.flagged) ? 'Yes' : 'No',
        `"${getIssuesText(h).replace(/"/g, '""')}"`
    ]);
    
    return [headers, ...rows].map(row => row.join(',')).join('\n');
}

// Get issues text
function getIssuesText(headline) {
    const issues = [];
    if (headline.moderation?.flagged) {
        issues.push('Content Moderation');
    }
    if (headline.compliance?.flagged && headline.compliance.issues) {
        issues.push(...headline.compliance.issues);
    }
    return issues.join('; ');
}

// Download file
function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast(`${filename} downloaded successfully!`);
}

// Loading states
function setAnalyzeLoading(loading) {
    const btnText = analyzeBtn.querySelector('.btn-text');
    const btnLoading = analyzeBtn.querySelector('.btn-loading');
    
    if (loading) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        analyzeBtn.disabled = true;
    } else {
        btnText.style.display = 'block';
        btnLoading.style.display = 'none';
        analyzeBtn.disabled = false;
    }
}

function setGenerateLoading(loading) {
    const generateBtn = document.getElementById('generateBtn');
    const btnText = generateBtn.querySelector('.btn-text');
    const btnLoading = generateBtn.querySelector('.btn-loading');
    
    if (loading) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        generateBtn.disabled = true;
    } else {
        btnText.style.display = 'block';
        btnLoading.style.display = 'none';
        generateBtn.disabled = false;
    }
}

function showLoadingOverlay(text) {
    document.getElementById('loadingText').textContent = text;
    loadingOverlay.style.display = 'flex';
}

function hideLoadingOverlay() {
    loadingOverlay.style.display = 'none';
}

// Error handling
function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    errorModal.style.display = 'flex';
}

function closeErrorModal() {
    errorModal.style.display = 'none';
}

// Toast notifications
function showToast(message, type = 'success') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Add to page
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Hide and remove toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

// Local storage
function saveToStorage() {
    // Disabled: We want the page to reset on refresh
    // const data = {
    //     articleData: currentArticleData,
    //     headlines: generatedHeadlines,
    //     timestamp: Date.now()
    // };
    // localStorage.setItem('headlinesGenerator', JSON.stringify(data));
}

function clearStorage() {
    // Clear any stored data to ensure fresh start
    localStorage.removeItem('headlinesGenerator');
}

function loadFromStorage() {
    try {
        const stored = localStorage.getItem('headlinesGenerator');
        if (stored) {
            const data = JSON.parse(stored);
            // Only load if less than 24 hours old
            if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
                if (data.articleData) {
                    currentArticleData = data.articleData;
                    
                    // Handle different input types
                    if (data.articleData.url === 'manual_input') {
                        // Switch to text mode and populate text area
                        switchInputMode('text');
                        const freeTextArea = document.getElementById('freeText');
                        if (freeTextArea) {
                            freeTextArea.value = data.articleData.content;
                        }
                    } else {
                        // Switch to URL mode and populate URL field
                        switchInputMode('url');
                        articleUrlInput.value = data.articleData.url;
                    }
                    
                    displayArticlePreview(data.articleData);
                    displayTemplates();
                    showNextSections();
                }
                if (data.headlines && data.headlines.length > 0) {
                    generatedHeadlines = data.headlines;
                    displayResults({
                        headlines: data.headlines,
                        total_headlines: data.headlines.length,
                        templates_used: [...new Set(data.headlines.map(h => h.template))],
                        article_language: data.articleData?.language || 'Unknown'
                    });
                }
            }
        }
    } catch (error) {
        console.error('Error loading from storage:', error);
    }
}

// Helper function to get language name from code
function getLanguageNameFromCode(code) {
    const languageNames = {
        'en': 'English',
        'he': 'Hebrew',
        'ar': 'Arabic',
        'ru': 'Russian',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'nl': 'Dutch',
        'sv': 'Swedish',
        'da': 'Danish',
        'no': 'Norwegian',
        'fi': 'Finnish',
        'pl': 'Polish',
        'cs': 'Czech',
        'sk': 'Slovak',
        'hu': 'Hungarian',
        'ro': 'Romanian',
        'bg': 'Bulgarian',
        'hr': 'Croatian',
        'sr': 'Serbian',
        'sl': 'Slovenian',
        'et': 'Estonian',
        'lv': 'Latvian',
        'lt': 'Lithuanian',
        'el': 'Greek',
        'tr': 'Turkish',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'hi': 'Hindi',
        'th': 'Thai',
        'vi': 'Vietnamese',
        'id': 'Indonesian',
        'ms': 'Malay',
        'tl': 'Filipino',
        'uk': 'Ukrainian',
        'be': 'Belarusian',
        'ka': 'Georgian',
        'hy': 'Armenian',
        'az': 'Azerbaijani',
        'kk': 'Kazakh',
        'ky': 'Kyrgyz',
        'uz': 'Uzbek',
        'fa': 'Persian',
        'ur': 'Urdu',
        'bn': 'Bengali',
        'ta': 'Tamil',
        'te': 'Telugu',
        'ml': 'Malayalam',
        'kn': 'Kannada',
        'gu': 'Gujarati',
        'pa': 'Punjabi',
        'mr': 'Marathi',
        'ne': 'Nepali',
        'si': 'Sinhala',
        'my': 'Burmese',
        'km': 'Khmer',
        'lo': 'Lao',
        'am': 'Amharic',
        'sw': 'Swahili',
        'zu': 'Zulu',
        'af': 'Afrikaans',
        'is': 'Icelandic',
        'mt': 'Maltese',
        'cy': 'Welsh',
        'ga': 'Irish',
        'eu': 'Basque',
        'ca': 'Catalan',
        'gl': 'Galician'
    };
    return languageNames[code] || 'English';
}

// Update total calculation display
function updateTotalCalculation() {
    const selectedTemplates = document.querySelectorAll('input[name="template"]:checked').length;
    const headlinesPerTemplate = parseInt(document.getElementById('nVariants').value) || 0;
    const total = selectedTemplates * headlinesPerTemplate;
    
    const totalCalculation = document.getElementById('totalCalculation');
    const totalHeadlinesCalc = document.getElementById('totalHeadlinesCalc');
    const headlinesPerTemplateSpan = document.getElementById('headlinesPerTemplate');
    const totalResult = document.getElementById('totalResult');
    
    if (totalHeadlinesCalc && headlinesPerTemplateSpan && totalResult) {
        totalHeadlinesCalc.textContent = selectedTemplates;
        headlinesPerTemplateSpan.textContent = headlinesPerTemplate;
        totalResult.textContent = total;
        
        if (selectedTemplates > 0 && headlinesPerTemplate > 0) {
            totalCalculation.style.display = 'block';
        } else {
            totalCalculation.style.display = 'none';
        }
    }
}

// Load countries from the server
async function loadCountries() {
    try {
        const response = await fetch('/api/geos');
        const data = await response.json();
        
        if (data.ok) {
            availableCountries = data.countries || [];
            populateCountrySelect();
            console.log('Loaded countries:', availableCountries.length, 'countries from Google Sheets');
        } else {
            console.error('Failed to load countries:', data.error);
        }
    } catch (error) {
        console.error('Error loading countries:', error);
    }
}

// Populate country select dropdown
function populateCountrySelect() {
    const countrySelect = document.getElementById('countryOverride');
    
    // Clear existing options except the first one
    while (countrySelect.children.length > 1) {
        countrySelect.removeChild(countrySelect.lastChild);
    }
    
    // Add country options from Google Sheets data
    availableCountries.forEach(country => {
        const option = document.createElement('option');
        option.value = country.geo;  // Use GEO code as value
        option.textContent = country.display;  // Show "Country Name (GEO)"
        countrySelect.appendChild(option);
    });
    
    console.log('Populated country dropdown with', availableCountries.length, 'countries');
}

// Handle country selection change
async function onCountryChange() {
    const selectedCountry = document.getElementById('countryOverride').value;
    const languageSelect = document.getElementById('languageOverride');
    const languageSearch = document.getElementById('languageSearch');
    
    // Clear language search when country changes to ensure proper option capture
    if (languageSearch) {
        languageSearch.value = '';
    }
    
    console.log('Country changed to:', selectedCountry);
    
    if (!selectedCountry) {
        console.log('No country selected, showing all languages');
        // Reset to all languages if no country selected
        await populateAllLanguages();
        return;
    }
    
    try {
        // Load languages for the selected country
        const response = await fetch(`/api/languages?geo=${encodeURIComponent(selectedCountry)}`);
        const data = await response.json();
        
        if (data.ok && data.languages && data.languages.length > 0) {
            // Clear current language options
            languageSelect.innerHTML = '<option value="">Use detected language</option>';
            
            // Add only languages available for this country
            data.languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                // Use the name from server if available, otherwise use our mapping
                const displayName = lang.name || getLanguageNameFromCode(lang.code);
                option.textContent = `${displayName} (${lang.code})`;
                languageSelect.appendChild(option);
            });
            
            // DON'T auto-select - keep "Use detected language" as default
            // This allows auto-detection to work properly
            languageSelect.value = "";
            
            console.log(`Updated language options for ${selectedCountry}:`, data.languages);
            console.log(`Keeping auto-detect enabled (no language pre-selected)`);
        } else {
            console.log(`No specific languages found for ${selectedCountry}, using all languages`);
            // Fallback to all languages if no specific languages found
            await populateAllLanguages();
        }
    } catch (error) {
        console.error('Error loading languages for country:', error);
        // Fallback to all languages on error
        await populateAllLanguages();
    }
}

// Populate language select with all available languages
async function populateAllLanguages() {
    const languageSelect = document.getElementById('languageOverride');
    
    try {
        console.log('🌍 Loading languages from API...');
        // Load all languages from server
        const response = await fetch('/api/languages');
        console.log('Languages API response status:', response.status);
        
        const data = await response.json();
        console.log('Languages API data keys:', Object.keys(data));
        console.log('Languages count:', data.languages ? data.languages.length : 'undefined');
        
        if (data.ok && data.languages) {
            // Clear existing options
            languageSelect.innerHTML = '<option value="">Use detected language</option>';
            
            availableLanguages = data.languages;

            // Add all languages from Google Sheets
            data.languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                option.textContent = `${lang.name} (${lang.code})`;
                languageSelect.appendChild(option);
            });
            
            console.log('Populated language dropdown with', data.languages.length, 'languages from Google Sheets');

            refreshDynamicLanguageSelects();
        } else {
            console.error('❌ Failed to load languages from server:', data.error);
            console.error('❌ API response data:', data);
            // Fallback to basic languages
            languageSelect.innerHTML = `
                <option value="">Use detected language</option>
                <option value="en">English (en)</option>
                <option value="he">Hebrew (he)</option>
                <option value="ar">Arabic (ar)</option>
                <option value="sv">Swedish (sv)</option>
            `;
            availableLanguages = [
                {code: 'en', name: 'English'},
                {code: 'he', name: 'Hebrew'},
                {code: 'ar', name: 'Arabic'},
                {code: 'sv', name: 'Swedish'}
            ];
            refreshDynamicLanguageSelects();
            console.log('⚠️ Using fallback languages due to API failure');
        }
    } catch (error) {
        console.error('Error loading languages:', error);
        // Fallback to basic languages
        languageSelect.innerHTML = `
            <option value="">Use detected language</option>
            <option value="en">English (en)</option>
            <option value="he">Hebrew (he)</option>
            <option value="ar">Arabic (ar)</option>
            <option value="sv">Swedish (sv)</option>
        `;
        availableLanguages = [
            {code: 'en', name: 'English'},
            {code: 'he', name: 'Hebrew'},
            {code: 'ar', name: 'Arabic'},
            {code: 'sv', name: 'Swedish'}
        ];
        refreshDynamicLanguageSelects();
    }
}

// Refresh templates manually
async function refreshTemplates() {
    const refreshBtn = document.getElementById('refreshTemplatesBtn');
    const refreshText = refreshBtn.querySelector('.refresh-text');
    const refreshLoading = refreshBtn.querySelector('.refresh-loading');
    
    // Set loading state
    refreshText.style.display = 'none';
    refreshLoading.style.display = 'flex';
    refreshBtn.disabled = true;
    
    try {
        console.log('Manually refreshing templates...');
        await loadTemplates();
        
        // If we have article data, redisplay templates
        if (currentArticleData) {
            displayTemplates();
        }
        
        showToast('Templates refreshed successfully!');
    } catch (error) {
        console.error('Error refreshing templates:', error);
        showToast('Failed to refresh templates', 'error');
    } finally {
        // Reset loading state
        refreshText.style.display = 'block';
        refreshLoading.style.display = 'none';
        refreshBtn.disabled = false;
    }
}

// Setup dropdown search functionality - filters dropdown as user types
function setupDropdownSearch(searchInputId, selectId) {
    const searchInput = document.getElementById(searchInputId);
    const select = document.getElementById(selectId);
    
    if (!searchInput || !select) {
        console.warn(`Dropdown search setup failed: ${searchInputId} or ${selectId} not found`);
        return;
    }
    
    // Store all options (captured fresh each time we need to filter)
    let allOptions = [];
    
    // Function to capture current options from the select
    const captureOptions = () => {
        allOptions = Array.from(select.options).map(opt => ({
            value: opt.value,
            text: opt.textContent
        }));
        console.log(`Captured ${allOptions.length} options for ${selectId}`);
    };
    
    // Observe changes to the select to recapture options when populated
    const observer = new MutationObserver(() => {
        const currentOptionsCount = select.options.length;
        const searchTerm = searchInput.value.trim();
        
        // Always recapture if:
        // 1. Search is empty, OR
        // 2. We have significantly more options than before (dropdown was repopulated)
        if (!searchTerm || currentOptionsCount > allOptions.length + 5) {
            console.log(`MutationObserver: Recapturing options for ${selectId}. Current: ${currentOptionsCount}, Stored: ${allOptions.length}, Search: "${searchTerm}"`);
            captureOptions();
        }
    });
    observer.observe(select, { childList: true });
    
    // Filter function - shows matching options while typing
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        
        // If search is empty, restore all options
        if (!searchTerm) {
            // Recapture options in case they changed
            if (allOptions.length <= 1) {
                captureOptions();
            }
            // Restore all options
            select.innerHTML = '';
            allOptions.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                select.appendChild(option);
            });
            return;
        }
        
        // Make sure we have options to filter
        if (allOptions.length <= 1) {
            captureOptions();
        }
        
        const currentValue = select.value;
        
        // Filter options
        select.innerHTML = '';
        
        // Always keep the first "empty" option
        const firstOpt = allOptions.find(opt => opt.value === '');
        if (firstOpt) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = firstOpt.text;
            select.appendChild(option);
        }
        
        // Add matching options
        let matchCount = 0;
        allOptions.forEach(opt => {
            if (opt.value !== '' && opt.text.toLowerCase().includes(searchTerm)) {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                if (opt.value === currentValue) {
                    option.selected = true;
                }
                select.appendChild(option);
                matchCount++;
            }
        });
        
        // If no matches found, show message
        if (matchCount === 0) {
            const noMatch = document.createElement('option');
            noMatch.value = '';
            noMatch.textContent = `No results for "${searchTerm}"`;
            noMatch.disabled = true;
            select.appendChild(noMatch);
        }
    });
    
    // When user selects an option, clear the search and restore all options
    select.addEventListener('change', function() {
        const selectedValue = this.value; // Capture value BEFORE any changes
        console.log(`Dropdown ${selectId} changed to: ${selectedValue}`);
        
        if (selectedValue) {
            searchInput.value = '';
            
            // Only restore if we have options to restore
            if (allOptions.length > 1) {
                // Restore all options so user can search again
                select.innerHTML = '';
                allOptions.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt.value;
                    option.textContent = opt.text;
                    if (opt.value === selectedValue) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
                // Ensure the value is set
                select.value = selectedValue;
                console.log(`Dropdown ${selectId} value confirmed: ${select.value}, allOptions: ${allOptions.length}`);
            } else {
                // allOptions is empty/minimal - don't clear, just log warning
                console.warn(`Dropdown ${selectId}: allOptions is empty (${allOptions.length}), NOT clearing dropdown`);
                // Try to recapture options now
                captureOptions();
                console.log(`Dropdown ${selectId}: Recaptured ${allOptions.length} options`);
            }
        }
    });
    
    // Initial capture after a delay to ensure dropdown is populated
    setTimeout(() => {
        if (allOptions.length <= 1) {
            captureOptions();
        }
    }, 1000);
    
    console.log(`✅ Dropdown search setup for ${searchInputId} -> ${selectId}`);
}

// Setup dropdown search for dynamic inputs (URL/Text inputs)
function setupDynamicDropdownSearch(searchInputId, selectId) {
    const searchInput = document.getElementById(searchInputId);
    const select = document.getElementById(selectId);
    
    if (!searchInput || !select) return;
    
    let allOptions = [];
    
    const captureOptions = () => {
        allOptions = Array.from(select.options).map(opt => ({
            value: opt.value,
            text: opt.textContent
        }));
        console.log(`Dynamic: Captured ${allOptions.length} options for ${selectId}`);
    };
    
    // Watch for options being populated - recapture when options significantly change
    const observer = new MutationObserver(() => {
        const currentOptionsCount = select.options.length;
        const searchTerm = searchInput.value.trim();
        
        if (!searchTerm || currentOptionsCount > allOptions.length + 5) {
            captureOptions();
        }
    });
    observer.observe(select, { childList: true });
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        
        if (!searchTerm) {
            if (allOptions.length <= 1) captureOptions();
            select.innerHTML = '';
            allOptions.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                select.appendChild(option);
            });
            return;
        }
        
        if (allOptions.length <= 1) captureOptions();
        
        const currentValue = select.value;
        select.innerHTML = '';
        
        // Keep first empty option
        const firstOpt = allOptions.find(opt => opt.value === '');
        if (firstOpt) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = firstOpt.text;
            select.appendChild(option);
        }
        
        allOptions.forEach(opt => {
            if (opt.value !== '' && opt.text.toLowerCase().includes(searchTerm)) {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                if (opt.value === currentValue) option.selected = true;
                select.appendChild(option);
            }
        });
    });
    
    select.addEventListener('change', function() {
        const selectedValue = this.value; // Capture value BEFORE changes
        console.log(`Dynamic dropdown ${selectId} changed to: ${selectedValue}`);
        
        if (selectedValue) {
            searchInput.value = '';
            
            // Only restore if we have options to restore
            if (allOptions.length > 1) {
                select.innerHTML = '';
                allOptions.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt.value;
                    option.textContent = opt.text;
                    if (opt.value === selectedValue) option.selected = true;
                    select.appendChild(option);
                });
                select.value = selectedValue;
                console.log(`Dynamic ${selectId} restored with ${allOptions.length} options`);
            } else {
                // allOptions is empty - don't clear, recapture
                console.warn(`Dynamic ${selectId}: allOptions empty (${allOptions.length}), NOT clearing`);
                captureOptions();
            }
        }
    });
    
    // Initial capture after delay
    setTimeout(() => {
        if (allOptions.length <= 1) {
            captureOptions();
        }
    }, 500);
}

// Filter templates based on search input
function filterTemplates() {
    const searchTerm = document.getElementById('templateSearch').value.toLowerCase().trim();
    
    if (!window.allTemplates) {
        return;
    }
    
    let filteredTemplates = window.allTemplates;
    
    if (searchTerm) {
        filteredTemplates = window.allTemplates.filter(template => 
            template.name.toLowerCase().includes(searchTerm) ||
            (template.description && template.description.toLowerCase().includes(searchTerm))
        );
    }
    
    // Clear current templates
    templatesContainer.innerHTML = '';
    
    // Render filtered templates
    filteredTemplates.forEach((template, index) => {
        const templateItem = document.createElement('div');
        templateItem.className = 'template-item';
        templateItem.innerHTML = `
            <label class="template-checkbox">
                <input type="checkbox" name="template" value="${template.id}" data-name="${template.name}">
                <span class="checkmark"></span>
                <div class="template-info">
                    <div class="template-name">${template.name}</div>
                    <div class="template-description">${template.description}</div>
                </div>
            </label>
        `;
        templatesContainer.appendChild(templateItem);
    });
    
    // Update template count
    updateTemplateCount(filteredTemplates.length);
    
    // Update calculation when templates change
    updateTotalCalculation();
}

// Update template count display
function updateTemplateCount(count) {
    const templateCountElement = document.getElementById('templateCount');
    if (templateCountElement) {
        templateCountElement.textContent = count;
    }
}

// Toggle select all templates
function toggleSelectAllTemplates() {
    const btn = document.getElementById('selectAllTemplatesBtn');
    const checkboxes = document.querySelectorAll('input[name="template"]');
    
    // Check if all are currently selected
    const allSelected = Array.from(checkboxes).every(cb => cb.checked);
    
    if (allSelected) {
        // Deselect all
        checkboxes.forEach(cb => cb.checked = false);
        btn.textContent = '☑️ Select All';
        btn.classList.remove('deselect');
    } else {
        // Select all
        checkboxes.forEach(cb => cb.checked = true);
        btn.textContent = '☐ Deselect All';
        btn.classList.add('deselect');
    }
    
    // Update calculation
    updateTotalCalculation();
}

// ========== NEW FUNCTIONS FOR MULTIPLE ARTICLES ==========

// Initialize dynamic inputs (URLs and Texts)
function initializeInputs() {
    console.log('🔧 Initializing dynamic inputs...');
    
    // Initialize with one URL input
    addUrlInput();
    
    // Initialize with one text input
    addTextInput();
    
    // Setup event listeners for new buttons
    const addUrlBtn = document.getElementById('addUrlBtn');
    const addTextBtn = document.getElementById('addTextBtn');
    const analyzeAllUrlsBtn = document.getElementById('analyzeAllUrlsBtn');
    const analyzeAllTextsBtn = document.getElementById('analyzeAllTextsBtn');
    
    if (addUrlBtn) {
        addUrlBtn.addEventListener('click', addUrlInput);
    }
    
    if (addTextBtn) {
        addTextBtn.addEventListener('click', addTextInput);
    }
    
    if (analyzeAllUrlsBtn) {
        analyzeAllUrlsBtn.addEventListener('click', analyzeAllUrls);
    }
    
    if (analyzeAllTextsBtn) {
        analyzeAllTextsBtn.addEventListener('click', analyzeAllTexts);
    }
    
    // Setup article navigation
    const prevArticleBtn = document.getElementById('prevArticleBtn');
    const nextArticleBtn = document.getElementById('nextArticleBtn');
    
    if (prevArticleBtn) {
        prevArticleBtn.addEventListener('click', showPreviousArticle);
    }
    
    if (nextArticleBtn) {
        nextArticleBtn.addEventListener('click', showNextArticle);
    }
    
    console.log('✅ Dynamic inputs initialized');
}

// Add URL input
function addUrlInput() {
    const container = document.getElementById('urlInputsContainer');
    const currentCount = container.children.length;
    
    if (currentCount >= maxInputs) {
        showToast('Maximum 10 URLs allowed', 'error');
        return;
    }
    
    const inputId = `urlInput_${currentCount}`;
    const wrapper = document.createElement('div');
    wrapper.className = 'input-group-wrapper';
    wrapper.id = `urlWrapper_${currentCount}`;
    
    wrapper.innerHTML = `
        <div class="input-wrapper">
            <input type="url" id="${inputId}" placeholder="https://example.com/article" class="article-url-input">
            <div style="display: flex; gap: 10px;">
                <div class="dynamic-searchable-container">
                    <input type="text" id="langSearch_${inputId}" class="dynamic-dropdown-search" placeholder="Search languages...">
                    <select id="lang_${inputId}" class="lang-override-select">
                        <option value="">Auto-detect language</option>
                    </select>
                </div>
                <div class="dynamic-searchable-container">
                    <input type="text" id="countrySearch_${inputId}" class="dynamic-dropdown-search" placeholder="Search countries...">
                    <select id="country_${inputId}" class="country-override-select">
                        <option value="">Auto-detect country</option>
                    </select>
                </div>
            </div>
        </div>
        ${currentCount > 0 ? `<button type="button" class="remove-input-btn" onclick="removeInput('urlWrapper_${currentCount}')">X Remove</button>` : ''}
    `;
    
    container.appendChild(wrapper);
    
    // Populate language and country dropdowns
    populateLanguageSelect(`lang_${inputId}`);
    populateCountrySelectForInput(`country_${inputId}`);
    
    // Setup search for dynamic dropdowns
    setTimeout(() => {
        setupDynamicDropdownSearch(`langSearch_${inputId}`, `lang_${inputId}`);
        setupDynamicDropdownSearch(`countrySearch_${inputId}`, `country_${inputId}`);
    }, 100);
    
    // Show/hide add button based on count
    updateAddButtonVisibility('url');
    
    // Add event listener for dynamic URL input
    const urlInput = document.getElementById(inputId);
    if (urlInput) {
        urlInput.addEventListener('input', function() {
            updateAddButtonVisibility('url');
        });
    }
}

// Add Text input
function addTextInput() {
    const container = document.getElementById('textInputsContainer');
    const currentCount = container.children.length;
    
    if (currentCount >= maxInputs) {
        showToast('Maximum 10 texts allowed', 'error');
        return;
    }
    
    const inputId = `textInput_${currentCount}`;
    const wrapper = document.createElement('div');
    wrapper.className = 'input-group-wrapper';
    wrapper.id = `textWrapper_${currentCount}`;
    
    wrapper.innerHTML = `
        <div class="input-wrapper">
            <textarea id="${inputId}" rows="6" placeholder="Paste or type your article content here..." class="article-text-input"></textarea>
            <div style="display: flex; gap: 10px;">
                <div class="dynamic-searchable-container">
                    <input type="text" id="langSearch_${inputId}" class="dynamic-dropdown-search" placeholder="Search languages...">
                    <select id="lang_${inputId}" class="lang-override-select">
                        <option value="">Auto-detect language</option>
                    </select>
                </div>
                <div class="dynamic-searchable-container">
                    <input type="text" id="countrySearch_${inputId}" class="dynamic-dropdown-search" placeholder="Search countries...">
                    <select id="country_${inputId}" class="country-override-select">
                        <option value="">Auto-detect country</option>
                    </select>
                </div>
            </div>
        </div>
        ${currentCount > 0 ? `<button type="button" class="remove-input-btn" onclick="removeInput('textWrapper_${currentCount}')">X Remove</button>` : ''}
    `;
    
    container.appendChild(wrapper);
    
    // Populate language and country dropdowns
    populateLanguageSelect(`lang_${inputId}`);
    populateCountrySelectForInput(`country_${inputId}`);
    
    // Setup search for dynamic dropdowns
    setTimeout(() => {
        setupDynamicDropdownSearch(`langSearch_${inputId}`, `lang_${inputId}`);
        setupDynamicDropdownSearch(`countrySearch_${inputId}`, `country_${inputId}`);
    }, 100);
    
    // Show/hide add button based on count
    updateAddButtonVisibility('text');
    
    // Add event listener for dynamic text input
    const textInput = document.getElementById(inputId);
    if (textInput) {
        textInput.addEventListener('input', function() {
            updateAddButtonVisibility('text');
        });
    }
}

// Remove input - Global scope for onclick
window.removeInput = function(wrapperId) {
    const wrapper = document.getElementById(wrapperId);
    if (wrapper) {
        wrapper.remove();
    }
    
    // Determine if it's URL or text
    const mode = wrapperId.startsWith('url') ? 'url' : 'text';
    updateAddButtonVisibility(mode);
}

// Update add button visibility
function updateAddButtonVisibility(mode) {
    const container = mode === 'url' ? document.getElementById('urlInputsContainer') : document.getElementById('textInputsContainer');
    const addBtn = mode === 'url' ? document.getElementById('addUrlBtn') : document.getElementById('addTextBtn');
    const currentCount = container.children.length;
    
    if (currentCount < maxInputs) {
        // Check if current inputs have values
        const inputs = mode === 'url' ? 
            container.querySelectorAll('.article-url-input') : 
            container.querySelectorAll('.article-text-input');
        
        const lastInput = inputs[inputs.length - 1];
        const hasValue = lastInput && lastInput.value.trim().length > 0;
        
        if (hasValue) {
            addBtn.style.display = 'block';
        } else {
            addBtn.style.display = 'none';
        }
    } else {
        addBtn.style.display = 'none';
    }
}

// Populate language select dropdown
function populateLanguageSelect(selectId, selectedValue = '') {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Always reset to base option first
    select.innerHTML = '<option value="">Auto-detect language</option>';

    const languages = (availableLanguages && availableLanguages.length > 0)
        ? availableLanguages
        : [
            {code: 'en', name: 'English'},
            {code: 'he', name: 'Hebrew'},
            {code: 'ar', name: 'Arabic'},
            {code: 'ru', name: 'Russian'},
            {code: 'es', name: 'Spanish'},
            {code: 'fr', name: 'French'},
            {code: 'de', name: 'German'},
            {code: 'sv', name: 'Swedish'},
            {code: 'ko', name: 'Korean'}
        ];
    
    languages.forEach(lang => {
        const option = document.createElement('option');
        option.value = lang.code;
        option.textContent = `${lang.name} (${lang.code})`;
        select.appendChild(option);
    });

    if (selectedValue) {
        select.value = selectedValue;
        if (select.value !== selectedValue) {
            select.value = '';
        }
    }
}

function refreshDynamicLanguageSelects() {
    const selects = document.querySelectorAll('.lang-override-select');
    selects.forEach(select => {
        const currentValue = select.value;
        populateLanguageSelect(select.id, currentValue);
    });
}

// Populate country select for input
function populateCountrySelectForInput(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Use available countries from global variable
    if (availableCountries && availableCountries.length > 0) {
        availableCountries.forEach(country => {
            const option = document.createElement('option');
            option.value = country.geo;
            option.textContent = country.display;
            select.appendChild(option);
        });
    }
}

// Analyze all URLs
async function analyzeAllUrls() {
    console.log('🔍 Analyzing all URLs...');
    const container = document.getElementById('urlInputsContainer');
    const inputs = container.querySelectorAll('.article-url-input');
    
    const urls = [];
    inputs.forEach((input, index) => {
        const url = input.value.trim();
        if (url) {
            // Use the actual input ID to find the correct override selects
            const inputId = input.id; // e.g., "urlInput_0"
            const langSelect = document.getElementById(`lang_${inputId}`);
            const countrySelect = document.getElementById(`country_${inputId}`);
            
            const langOverride = langSelect?.value || '';
            const countryOverride = countrySelect?.value || '';
            
            console.log(`📝 URL ${index}: langOverride=${langOverride}, countryOverride=${countryOverride}`);
            console.log(`   Select IDs: lang_${inputId}, country_${inputId}`);
            console.log(`   Lang select found: ${!!langSelect}, Country select found: ${!!countrySelect}`);
            
            urls.push({url, langOverride, countryOverride, index: inputId});
        }
    });
    
    if (urls.length === 0) {
        showError('Please enter at least one URL');
        return;
    }
    
    setAnalyzeAllLoading(true, 'url');
    showLoadingOverlay(`Analyzing ${urls.length} URL(s)...`);
    
    currentArticlesData = [];
    
    for (let i = 0; i < urls.length; i++) {
        const {url, langOverride, countryOverride, index} = urls[i];
        try {
            const response = await fetch('/api/scrape-article', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });
            
            const data = await response.json();
            
            if (data.ok) {
                let articleData = data.article;
                articleData.inputIndex = index;
                
                // Apply overrides
                if (langOverride) {
                    articleData.language_code = langOverride;
                    articleData.language = getLanguageNameFromCode(langOverride);
                }
                if (countryOverride) {
                    articleData.detected_country_geo = countryOverride;
                    articleData.detected_country = availableCountries.find(c => c.geo === countryOverride)?.name || countryOverride;
                }
                
                currentArticlesData.push(articleData);
            } else {
                showToast(`Failed to analyze URL ${i + 1}: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error(`Error analyzing URL ${i + 1}:`, error);
            showToast(`Error analyzing URL ${i + 1}`, 'error');
        }
    }
    
    setAnalyzeAllLoading(false, 'url');
    hideLoadingOverlay();
    
    if (currentArticlesData.length > 0) {
        displayMultipleArticles();
        displayTemplates();
        showNextSections();
        showToast(`Successfully analyzed ${currentArticlesData.length} article(s)!`);
    } else {
        showError('Failed to analyze any articles. Please check the URLs and try again.');
    }
}

// Analyze all texts
async function analyzeAllTexts() {
    console.log('📝 Analyzing all texts...');
    const container = document.getElementById('textInputsContainer');
    const inputs = container.querySelectorAll('.article-text-input');
    
    const texts = [];
    inputs.forEach((input, index) => {
        const text = input.value.trim();
        if (text && text.length >= 100) {
            // Use the actual input ID to find the correct override selects
            const inputId = input.id; // e.g., "textInput_0"
            const langSelect = document.getElementById(`lang_${inputId}`);
            const countrySelect = document.getElementById(`country_${inputId}`);
            
            const langOverride = langSelect?.value || '';
            const countryOverride = countrySelect?.value || '';
            
            console.log(`📝 Text ${index}: langOverride=${langOverride}, countryOverride=${countryOverride}`);
            
            texts.push({text, langOverride, countryOverride, index: inputId});
        }
    });
    
    if (texts.length === 0) {
        showError('Please enter at least one text (minimum 100 characters)');
        return;
    }
    
    setAnalyzeAllLoading(true, 'text');
    showLoadingOverlay(`Analyzing ${texts.length} text(s)...`);
    
    currentArticlesData = [];
    
    for (let i = 0; i < texts.length; i++) {
        const {text, langOverride, countryOverride, index} = texts[i];
        try {
            const response = await fetch('/api/scrape-article', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text})
            });
            
            const data = await response.json();
            
            if (data.ok) {
                let articleData = data.article;
                articleData.inputIndex = index;
                
                // Apply overrides
                if (langOverride) {
                    articleData.language_code = langOverride;
                    articleData.language = getLanguageNameFromCode(langOverride);
                }
                if (countryOverride) {
                    articleData.detected_country_geo = countryOverride;
                    articleData.detected_country = availableCountries.find(c => c.geo === countryOverride)?.name || countryOverride;
                }
                
                currentArticlesData.push(articleData);
            } else {
                showToast(`Failed to analyze text ${i + 1}: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error(`Error analyzing text ${i + 1}:`, error);
            showToast(`Error analyzing text ${i + 1}`, 'error');
        }
    }
    
    setAnalyzeAllLoading(false, 'text');
    hideLoadingOverlay();
    
    if (currentArticlesData.length > 0) {
        displayMultipleArticles();
        displayTemplates();
        showNextSections();
        showToast(`Successfully analyzed ${currentArticlesData.length} text(s)!`);
    } else {
        showError('Failed to analyze any texts. Please check the content and try again.');
    }
}

// Display multiple articles
function displayMultipleArticles() {
    const articlesPreview = document.getElementById('articlesPreview');
    const articlesListContainer = document.getElementById('articlesListContainer');
    const articlesCount = document.getElementById('articlesCount');
    
    articlesCount.textContent = currentArticlesData.length;
    articlesListContainer.innerHTML = '';
    
    currentArticlesData.forEach((article, index) => {
        const card = document.createElement('div');
        card.className = 'article-preview-card';
        
        // Create preview (first 300 chars)
        const contentPreview = article.content.substring(0, 300);
        const hasMore = article.content.length > 300;
        
        card.innerHTML = `
            <h4>${index + 1}. ${article.title || 'Untitled'}</h4>
            <div class="article-meta">
                <span><span class="meta-label">Language:</span> ${article.language} (${article.language_code})</span>
                <span><span class="meta-label">Country:</span> ${article.detected_country || 'Not detected'}</span>
                <span><span class="meta-label">Source:</span> ${article.source || 'unknown'}</span>
                <span><span class="meta-label">Length:</span> ${article.content.length} chars</span>
            </div>
            <div class="article-content-section">
                <div class="article-content-label">Content Preview:</div>
                <div class="article-content-preview" id="content_${index}">
                    ${contentPreview}${hasMore ? '...' : ''}
                </div>
                ${hasMore ? `
                    <button type="button" class="read-more-article-btn" id="readMore_${index}" onclick="toggleArticleContent(${index})">
                        <span class="read-more-text">📖 Read Full Content</span>
                        <span class="read-less-text" style="display: none;">📕 Show Less</span>
                    </button>
                ` : ''}
            </div>
        `;
        
        articlesListContainer.appendChild(card);
        
        // Store full content in data attribute
        if (hasMore) {
            const contentDiv = card.querySelector(`#content_${index}`);
            contentDiv.setAttribute('data-full-content', article.content);
            contentDiv.setAttribute('data-preview', contentPreview + '...');
        }
    });
    
    articlesPreview.style.display = 'block';
    
    // Hide single article preview
    document.getElementById('articlePreview').style.display = 'none';
}

// Toggle article content (expand/collapse) - Global scope for onclick
window.toggleArticleContent = function(index) {
    const contentDiv = document.getElementById(`content_${index}`);
    const btn = document.getElementById(`readMore_${index}`);
    const readMoreText = btn.querySelector('.read-more-text');
    const readLessText = btn.querySelector('.read-less-text');
    
    const fullContent = contentDiv.getAttribute('data-full-content');
    const preview = contentDiv.getAttribute('data-preview');
    
    const isExpanded = contentDiv.classList.contains('expanded');
    
    if (isExpanded) {
        // Collapse
        contentDiv.textContent = preview;
        contentDiv.classList.remove('expanded');
        readMoreText.style.display = 'inline';
        readLessText.style.display = 'none';
    } else {
        // Expand
        contentDiv.textContent = fullContent;
        contentDiv.classList.add('expanded');
        readMoreText.style.display = 'none';
        readLessText.style.display = 'inline';
    }
}

// Set analyze all loading state
function setAnalyzeAllLoading(loading, mode) {
    const btn = mode === 'url' ? document.getElementById('analyzeAllUrlsBtn') : document.getElementById('analyzeAllTextsBtn');
    if (!btn) return;
    
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');
    
    if (loading) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        btn.disabled = true;
    } else {
        btnText.style.display = 'block';
        btnLoading.style.display = 'none';
        btn.disabled = false;
    }
}

// Article navigation functions
function showPreviousArticle() {
    const currentIndex = currentArticlesData.findIndex(a => a === currentArticleFilter);
    if (currentIndex > 0) {
        filterResultsByArticle(currentIndex - 1);
    } else {
        // Wrap around to last article
        filterResultsByArticle(currentArticlesData.length - 1);
    }
}

function showNextArticle() {
    const currentIndex = currentArticlesData.findIndex(a => a === currentArticleFilter);
    if (currentIndex < currentArticlesData.length - 1) {
        filterResultsByArticle(currentIndex + 1);
    } else {
        // Wrap around to first article
        filterResultsByArticle(0);
    }
}

function filterResultsByArticle(articleIndex) {
    console.log('Filtering by article index:', articleIndex);
    currentArticleFilter = currentArticlesData[articleIndex];
    console.log('Current filter set to:', currentArticleFilter);
    refreshResultsDisplay();
}

function refreshResultsDisplay() {
    console.log('Refreshing display with filter:', currentArticleFilter);
    console.log('Total headlines:', generatedHeadlines.length);
    
    // Always filter by specific article (no "all" mode)
    let headlinesToDisplay = generatedHeadlines;
    
    if (currentArticlesData.length > 0) {
        const articleIndex = currentArticlesData.indexOf(currentArticleFilter);
        console.log('Filtering for article index:', articleIndex);
        
        if (articleIndex >= 0) {
            headlinesToDisplay = generatedHeadlines.filter(h => h.articleIndex === articleIndex);
            console.log('Filtered headlines count:', headlinesToDisplay.length);
        }
    }
    
    displayResults({
        headlines: headlinesToDisplay,
        total_headlines: headlinesToDisplay.length,
        templates_used: [...new Set(headlinesToDisplay.map(h => h.template))],
        article_language: currentArticleFilter.language || (currentArticlesData[0]?.language || 'Unknown')
    });
    
    // Update navigation UI
    updateNavigationUI();
}

function updateNavigationUI() {
    const navigation = document.getElementById('articleNavigation');
    const currentTitle = document.getElementById('currentArticleTitle');
    const currentIndex = document.getElementById('currentArticleIndex');
    const totalCount = document.getElementById('totalArticlesCount');
    const prevBtn = document.getElementById('prevArticleBtn');
    const nextBtn = document.getElementById('nextArticleBtn');
    
    console.log('Updating navigation UI, articles count:', currentArticlesData.length);
    
    if (currentArticlesData.length > 1) {
        navigation.style.display = 'flex';
        
        const index = currentArticlesData.indexOf(currentArticleFilter);
        const title = currentArticleFilter.title || `Article ${index + 1}`;
        // Truncate title if too long
        const displayTitle = title.length > 50 ? title.substring(0, 50) + '...' : title;
        currentTitle.textContent = displayTitle;
        currentIndex.textContent = index + 1;
        totalCount.textContent = currentArticlesData.length;
        
        // Always enable both buttons (wrap around)
        prevBtn.disabled = false;
        nextBtn.disabled = false;
        
        console.log('Navigation visible, showing article:', index + 1);
    } else {
        navigation.style.display = 'none';
        console.log('Navigation hidden (single article)');
    }
}