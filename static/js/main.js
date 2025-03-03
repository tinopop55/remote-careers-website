// Remote Coaching Academy - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Set initial language based on localStorage or default to Romanian
    const savedLanguage = localStorage.getItem('preferredLanguage') || 'ro';
    switchLanguage(savedLanguage);
    
    // Highlight the current page in the navigation
    highlightCurrentPage();
    
    // Initialize animation on scroll
    initAnimations();
    
    // Initialize any dropdowns
    initDropdowns();
});

/**
 * Switch language between Romanian and English
 * @param {string} lang - The language code ('ro' or 'en')
 */
function switchLanguage(lang) {
    // Store the preferred language
    localStorage.setItem('preferredLanguage', lang);
    
    // Update language elements visibility
    document.querySelectorAll('.en, .ro').forEach(el => {
        el.style.display = 'none';
    });
    
    document.querySelectorAll('.' + lang).forEach(el => {
        el.style.display = 'inline';
    });
    
    // Update active button
    const roBtnElements = document.querySelectorAll('.ro-btn');
    const enBtnElements = document.querySelectorAll('.en-btn');
    
    roBtnElements.forEach(btn => {
        btn.classList.toggle('active', lang === 'ro');
    });
    
    enBtnElements.forEach(btn => {
        btn.classList.toggle('active', lang === 'en');
    });
    
    // Update language input for forms
    const langInputs = document.querySelectorAll('input[name="language"]');
    langInputs.forEach(input => {
        input.value = lang;
    });
    
    // Set html lang attribute
    document.documentElement.setAttribute('lang', lang);
}

/**
 * Highlight the current page in the navigation
 */
function highlightCurrentPage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPath || (currentPath.startsWith(href) && href !== '/')) {
            link.classList.add('active');
            
            // If it's in a dropdown, also highlight the parent
            const parentDropdown = link.closest('.dropdown');
            if (parentDropdown) {
                const parentLink = parentDropdown.querySelector('.dropdown-toggle');
                if (parentLink) {
                    parentLink.classList.add('active');
                }
            }
        }
    });
}

/**
 * Initialize animations for elements with animation classes
 */
function initAnimations() {
    const animatedElements = document.querySelectorAll('.animate-up, .animate-left, .animate-right');
    
    // Check if element is in viewport
    function isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.bottom >= 0
        );
    }
    
    // Add in-view class to elements in viewport
    function checkAnimations() {
        animatedElements.forEach(element => {
            if (isInViewport(element)) {
                element.classList.add('in-view');
            }
        });
    }
    
    // Check on load
    checkAnimations();
    
    // Check on scroll
    window.addEventListener('scroll', checkAnimations);
}

/**
 * Initialize Bootstrap dropdowns
 */
function initDropdowns() {
    const dropdownElementList = document.querySelectorAll('.dropdown-toggle');
    dropdownElementList.forEach(function(dropdownToggleEl) {
        dropdownToggleEl.addEventListener('click', function(e) {
            const dropdownMenu = this.nextElementSibling;
            if (dropdownMenu.classList.contains('show')) {
                dropdownMenu.classList.remove('show');
            } else {
                // Close any open dropdowns first
                document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
                    menu.classList.remove('show');
                });
                dropdownMenu.classList.add('show');
            }
            e.stopPropagation();
        });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function() {
        document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
            menu.classList.remove('show');
        });
    });
}

/**
 * Handle file upload preview
 * @param {HTMLElement} input - The file input element
 * @param {string} previewId - ID of the preview element
 */
function handleFileUpload(input, previewId) {
    const preview = document.getElementById(previewId);
    if (!preview) return;
    
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const fileName = file.name;
        preview.textContent = fileName;
        preview.parentElement.classList.add('file-selected');
    }
}

/**
 * Show loading indicator
 * @param {string} loadingId - ID of the loading element
 * @param {boolean} show - Whether to show or hide the indicator
 */
function showLoading(loadingId, show) {
    const loading = document.getElementById(loadingId);
    if (!loading) return;
    
    loading.style.display = show ? 'block' : 'none';
}

/**
 * Format a date string
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date string
 */
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

/**
 * Scroll to element
 * @param {string} elementId - ID of the element to scroll to
 */
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Validate Email
 * @param {string} email - Email to validate
 * @returns {boolean} Is valid email
 */
function isValidEmail(email) {
    const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(String(email).toLowerCase());
}

/**
 * Handle CV analysis form submission
 * @param {HTMLFormElement} form - The form element
 * @param {Function} callback - Callback function after form submission
 */
function handleCvAnalysisForm(form, callback) {
    // Form validation
    const emailInput = form.querySelector('input[name="email"]');
    const fileInput = form.querySelector('input[type="file"]');
    
    if (!emailInput || !fileInput) return;
    
    const email = emailInput.value.trim();
    const file = fileInput.files[0];
    
    if (!isValidEmail(email)) {
        alert('Please enter a valid email address.');
        return;
    }
    
    if (!file) {
        alert('Please select a CV file to upload.');
        return;
    }
    
    // Show loading
    showLoading('loading-indicator', true);
    
    // Create FormData
    const formData = new FormData(form);
    
    // Send form data
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        showLoading('loading-indicator', false);
        if (callback && typeof callback === 'function') {
            callback(data);
        }
    })
    .catch(error => {
        showLoading('loading-indicator', false);
        console.error('Error:', error);
        alert('An error occurred. Please try again later.');
    });
} 