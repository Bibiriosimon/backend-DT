
document.addEventListener('DOMContentLoaded', () => {
    // 检查浏览器是否支持语音识别API
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        runApp();
    } else {
        showUnsupportedBrowserWarning();
    }
});

// 如果浏览器不支持，显示警告信息
function showUnsupportedBrowserWarning() {
    document.querySelector('.controls').style.display = 'none';
    document.querySelector('.view-container').style.display = 'none';
    document.getElementById('statusIndicator').style.display = 'none';
    const mainElement = document.querySelector('main') || document.body;
    const warningMessage = document.createElement('div');
    warningMessage.className = 'unsupported-browser-warning';
    warningMessage.innerHTML = `<h2>抱歉，您的浏览器不支持语音识别功能</h2><p>为了获得最佳体验，我们推荐使用最新版本的 <strong>Google Chrome</strong>, <strong>Microsoft Edge</strong>, 或 <strong>Safari</strong> 浏览器。</p>`;
    mainElement.insertBefore(warningMessage, mainElement.firstChild);
}

// 主应用逻辑
function runApp() {
    // --- DOM 元素获取 ---
    const controlBtn = document.getElementById('controlBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const liveContentOutput = document.getElementById('liveContentOutput');
    const noteOutput = document.getElementById('noteOutput');
    const views = document.querySelectorAll('.view-container');
    const transBtn = document.getElementById('transBtn');
    const noteBtn = document.getElementById('noteBtn');
    const vocabBtn = document.getElementById('vocabBtn');
    const vocabListContainer = document.getElementById('vocabListContainer');
    const popupOverlay = document.getElementById('popupOverlay');
    const dictionaryPopup = document.getElementById('dictionaryPopup');
    const popupContent = document.getElementById('popupContent');
    const addVocabBtn = document.getElementById('addVocabBtn');
    const aiContextSearchBtn = document.getElementById('aiContextSearchBtn');
    const aiPopup = document.getElementById('aiPopup');
    const aiPopupContent = document.getElementById('aiPopupContent');
    const timeoutWarningPopup = document.getElementById('timeoutWarningPopup');
    const resumeBtn = document.getElementById('resumeBtn');
    const endSessionBtn = document.getElementById('endSessionBtn');
    const statusIndicator = document.getElementById('statusIndicator');
    const waveIndicator = document.getElementById('waveIndicator');
    const pauseIndicator = document.getElementById('pauseIndicator');
    const courseNameModal = document.getElementById('courseNameModal');
    const courseNameInput = document.getElementById('courseNameInput');
    const modalConfirmBtn = document.getElementById('modalConfirmBtn');
    const modalCancelBtn = document.getElementById('modalCancelBtn');
    const modeSwitch = document.getElementById('mode-switch');
    const modeIndicator = document.getElementById('mode-indicator');
    const spinnerOverlay = document.getElementById('spinnerOverlay');
    const spinnerMessage = document.getElementById('spinnerMessage');

    // --- API & 配置 ---
    const BACKEND_API_BASE_URL = 'http://127.0.0.1:5001'; // 我们后端的地址
    const DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions';
    const DEEPL_API_URL = 'https://api-free.deepl.com/v2/translate';

    // --- 状态管理 ---
    let recognition;
    let isListening = false, isPaused = false, hasStarted = false;
    let vocabularyList = [];
    let currentPopupData = { word: null, contextSentence: null, definitionData: null };
    let inactivityTimer = null, warningTimer = null;
    const INACTIVITY_TIMEOUT = 60000;
    let classCount = 0, classStartTime = null;
    let noteBuffer = "", fullTranscriptHistory = "";
    let currentCourseName = "通用课程";
    let currentOriginalP = null, currentTranslationP = null;
    let interimTranslationTimer = null;
    let isFullPowerMode = false;

    // ==========================================================
    // --- 核心函数 ---
    // ==========================================================

 // --- 替换这个函数 ---

function initializeRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    

    recognition.interimResults = true; 

    recognition.onresult = handleRecognitionResult;
    recognition.onstart = handleRecognitionStart;
    recognition.onend = handleRecognitionEnd;
    recognition.onerror = handleRecognitionError;
    console.log("新的语音识别引擎已初始化 (强制开启 Interim Results)。");
}

    function startListening() {
        if (isListening && !isPaused && recognition) {
            try {
                recognition.start();
                console.log("语音识别已启动。");
            } catch (error) {
                console.error("启动语音识别失败:", error);
                setTimeout(() => { try { recognition.start(); } catch(e){ console.error("重试启动失败:", e); } }, 250);
            }
        }
    }

    function showSpinner(message) {
        spinnerMessage.innerHTML = message;
        spinnerOverlay.style.display = 'flex';
    }

    function hideSpinner() {
        spinnerOverlay.style.display = 'none';
    }
    
    async function generateAndApplyGrammar(courseName) {
    console.log(`开始为主题 "${courseName}" 生成专业词汇列表...`);
    try {
        const prompt = `你是一个专家教授，在所有研究领域有着超人的见解。请为语音识别引擎生成JSGF格式的语法。我将给你一个课程主题，请你围绕这个主题，生成一个包含大约50个最核心、最专业、最可能被频繁提及的英文术语列表。输出要求：1. 每个术语必须是英文。2. 用 "|" 符号将每个术语隔开。3. 不要添加任何额外的解释、标题、编号或换行符，直接输出由 "|" 分隔的单个长字符串。课程主题是：${courseName}`;
        
        // 【修改点在这里】
        const response = await fetch(`${BACKEND_API_BASE_URL}/api/deepseek-chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }, // 移除了 'Authorization'
            body: JSON.stringify({ model: 'deepseek-chat', messages: [{ role: 'user', content: prompt }], max_tokens: 1024, temperature: 0.5 })
        });
        
        if (!response.ok) { const errorData = await response.json(); throw new Error(`API 请求失败: ${errorData.error.message}`); }
        const data = await response.json();
        const grammarTerms = data.choices[0].message.content.trim();
        if (grammarTerms) {
            const grammar = `#JSGF V1.0; grammar courseTerms; public <term> = ${grammarTerms};`;
            const SpeechGrammarList = window.SpeechGrammarList || window.webkitSpeechGrammarList;
            const speechRecognitionList = new SpeechGrammarList();
            speechRecognitionList.addFromString(grammar, 1);
            recognition.grammars = speechRecognitionList;
            console.log("识别引擎已优化。加载的词汇:", grammarTerms);
            return true;
        } else { throw new Error("API 返回了空的词汇列表。"); }
    } catch (error) {
        console.error('优化识别引擎失败:', error);
        const SpeechGrammarList = window.SpeechGrammarList || window.webkitSpeechGrammarList;
        if (recognition) recognition.grammars = new SpeechGrammarList();
        return false;
    }
}


    async function getAITranslation(text, courseName) {
    const system_prompt = `You are a world-class simultaneous interpreter specializing in academic lectures. Your task is to translate English lecture snippets into fluent, accurate, and professional Chinese. Your entire response must be ONLY the Chinese translation. Do not add any extra words, explanations, or punctuation outside of the translation itself.`;
    const user_prompt = `The lecture topic is "${courseName}". Prioritize terminology and phrasing suitable for this academic field. Please provide a professional Chinese translation for the following English text:\n\n"${text}"`;
    try {
        // 【修改点在这里】
        const response = await fetch(`${BACKEND_API_BASE_URL}/api/deepseek-chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }, // 移除了 'Authorization'
            body: JSON.stringify({ model: 'deepseek-chat', messages: [ { role: 'system', content: system_prompt }, { role: 'user', content: user_prompt } ], temperature: 0.1, stream: false })
        });
        
        if (!response.ok) throw new Error(`DeepSeek API Translation API error! status: ${response.status}`);
        const data = await response.json();
        return data.choices?.[0]?.message.content.trim().replace(/^"|"$/g, '') || null;
    } catch (error) { console.error("DeepSeek AI Translation fetch error:", error); return null; }
}

    // 新版本：通过我们自己的后端进行翻译
async function getFastTranslation(textToTranslate, targetLang = 'ZH') {
    if (!textToTranslate || textToTranslate.trim() === "") return "";

    // 新的API地址，指向我们的后端
    const apiUrl = `${BACKEND_API_BASE_URL}/api/deepl-translate`; 

    // 请求体现在是JSON格式，而不是URLSearchParams
    const body = JSON.stringify({
        text: textToTranslate,
        target_lang: targetLang
    });

    // 请求头也相应改变
    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: body
    };

    try {
        const response = await fetch(apiUrl, options);
        
        // 我们不再需要处理 403 CORS Proxy 错误，代码更简洁了！
        if (response.status === 429) { 
            return "（翻译服务额度用尽）"; 
        }
        if (!response.ok) {
            // 尝试从后端获取更详细的错误信息
            const errorData = await response.json();
            console.error("后端代理返回错误:", errorData);
            throw new Error(`后端代理错误: ${errorData.error || '未知错误'}`);
        }

        const result = await response.json();
        // DeepL的原始返回结果是 { "translations": [...] }
        // 我们直接从中提取需要的文本
        return result.translations?.[0]?.text || "...";

    } catch (error) {
        console.error("调用后端翻译代理时出错:", error);
        return "翻译接口出错";
    }
}

    
    // 请用此版本替换您 JS 文件中现有的 summarizeTextForNote 函数
async function summarizeTextForNote(text, courseName) {
    if (!text || text.trim().length === 0) { return; }
  
    const originalButtonText = noteBtn.innerHTML;
    noteBtn.disabled = true;
    noteBtn.classList.add('note-btn-loading'); 
    noteBtn.innerHTML = `
        <div class="loader-wrapper">
            <span class="loader-letter">G</span>
            <span class="loader-letter">e</span>
            <span class="loader-letter">n</span>
            <span class="loader-letter">e</span>
            <span class="loader-letter">r</span>
            <span class="loader-letter">a</span>
            <span class="loader-letter">t</span>
            <span class="loader-letter">i</span>
            <span class="loader-letter">n</span>
            <span class="loader-letter">g</span>
            <div class="loader"></div>
        </div>`;

    const prompt = `You are a highly efficient note-taking assistant for a university lecture on "${courseName}". Please summarize the key points from the following transcript for a student's review. You can expand on the points where necessary. Please use Chinese for your response. The summary should be concise, well-structured, and use **bold text** to highlight key terms.\n\nTranscript content:\n"${text}"`;
  
    try {
        // 【修改点在这里】
        const response = await fetch(`${BACKEND_API_BASE_URL}/api/deepseek-chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }, // 移除了 'Authorization'
            body: JSON.stringify({ model: 'deepseek-chat', messages: [{ role: 'user', content: prompt }], temperature: 0.5 })
        });

        if (!response.ok) throw new Error(`DeepSeek API error! status: ${response.status}`);
        const data = await response.json();
        if (data.choices && data.choices.length > 0) { addNoteEntry(data.choices[0].message.content); } else { addNoteEntry("未能生成笔记摘要。"); }
    } catch (error) {
        console.error("DeepSeek API fetch error for note summarization:", error);
        addNoteEntry("生成笔记时发生网络错误(DeepSeek)。");
    } finally {
        noteBtn.disabled = false;
        noteBtn.classList.remove('note-btn-loading');
        noteBtn.innerHTML = originalButtonText;
    }
}

    function handleRecognitionStart() {
        console.log('事件: onstart - 识别服务已连接。');
        isListening = true;
        startInactivityCountdown();
        controlBtn.textContent = '结束课程';
        controlBtn.classList.add('active');
        pauseBtn.disabled = false;
        pauseBtn.textContent = '暂停';
        pauseBtn.className = 'btn pausable';
        liveContentOutput.classList.add('listening');
        updateStatusIndicator('listening');
    }

    function handleRecognitionEnd() {
        console.log(`事件: onend - 识别服务已断开。isListening: ${isListening}, isPaused: ${isPaused}`);
        liveContentOutput.classList.remove('listening');
        if (isListening && !isPaused) {
            console.log("非暂停状态下断开，自动重启...");
            startListening();
        }
    }

    function handleRecognitionError(event) {
        console.error(`语音识别错误: ${event.error}`);
        if(event.error === 'no-speech') {
             // 无语音是常见情况，让onend去处理重启
        } else if (event.error === 'network') {
            updateStatusIndicator('error', '网络错误');
        } else {
            updateStatusIndicator('stopped');
        }
    }
    
 // --- 替换这个函数 ---

function handleRecognitionResult(event) {
    startInactivityCountdown();
    let interimTranscript = '', finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
        } else {
            interimTranscript += event.results[i][0].transcript;
        }
    }

    // ✅【核心修改 2】重构逻辑
    // 逻辑：只要有 interim 结果，就无条件地更新屏幕上的英文原文。
    if (interimTranscript) {
        // 如果是新的一句话，先创建 DOM 元素
        if (!currentOriginalP) {
            currentOriginalP = document.createElement('p');
            currentOriginalP.className = 'original-text new-entry';
            liveContentOutput.appendChild(currentOriginalP);

            currentTranslationP = document.createElement('p');
            currentTranslationP.className = 'translation-text new-entry';
            // 在经济模式下，这里只显示一个占位符，直到句子结束
            currentTranslationP.innerHTML = `<span class="interim-translation">...</span>`; 
            liveContentOutput.appendChild(currentTranslationP);
            
            setTimeout(() => {
                currentOriginalP.classList.add('visible');
                currentTranslationP.classList.add('visible');
            }, 10);
        }
        
        // 实时更新英文原文的显示
        currentOriginalP.innerHTML = `<span class="word">${fullTranscriptHistory}</span><span class="word interim-word">${interimTranscript}</span>`;

        // **关键区别**：只在“满血模式”下才对 interim 结果进行翻译
        if (isFullPowerMode) {
            clearTimeout(interimTranslationTimer);
            interimTranslationTimer = setTimeout(async () => {
                if (currentTranslationP && interimTranscript) {
                    const fastText = await getFastTranslation(interimTranscript);
                    if(currentTranslationP) { 
                        const finalPart = currentTranslationP.dataset.final_translation || "";
                        currentTranslationP.innerHTML = finalPart + `<span class="interim-translation">${fastText || " ..."}</span>`; 
                    }
                }
            }, 800); // 延迟800ms避免过于频繁的API请求
        }
    }

    // 逻辑：当一句话最终确定后，对两个模式都执行最终翻译。
    if (finalTranscript) {
        clearTimeout(interimTranslationTimer); // 停止任何可能在进行的 interim 翻译

        fullTranscriptHistory += finalTranscript;
        noteBuffer += finalTranscript; 
        
        // 确保 DOM 元素存在 (应对那些非常短、直接final的句子)
        if (!currentOriginalP) {
            currentOriginalP = document.createElement('p');
            currentOriginalP.className = 'original-text new-entry visible';
            liveContentOutput.appendChild(currentOriginalP);
            currentTranslationP = document.createElement('p');
            currentTranslationP.className = 'translation-text new-entry visible';
            liveContentOutput.appendChild(currentTranslationP);
        }

        // 更新并最终确定英文原文
        const words = fullTranscriptHistory.split(/\s+/).filter(Boolean).map(word => `<span class="word">${word} </span>`).join('');
        currentOriginalP.innerHTML = words;
        currentOriginalP.classList.remove('new-entry');

        const finalP = currentTranslationP;
        const fullSentence = fullTranscriptHistory;

        // 两个模式下都获取最终翻译
        getFastTranslation(fullSentence).then(fastText => {
            if (finalP) finalP.innerHTML = `${fastText} <span class="ai-thinking-indicator">...</span>`;
            autoScrollView();
        });
        getAITranslation(fullSentence, currentCourseName).then(aiText => {
            if (aiText && finalP) {
                finalP.innerHTML = aiText;
                finalP.classList.add('ai-enhanced');
            } else if (finalP) {
                finalP.querySelector('.ai-thinking-indicator')?.remove();
            }
        });
        
        if (finalP) {
            finalP.dataset.final_translation = ''; // 清空，为下一句的 interim 翻译做准备
            finalP.classList.remove('new-entry');
        }

        // 为下一句话重置状态
        currentOriginalP = null;
        currentTranslationP = null;
        fullTranscriptHistory = "";
    }
    
    // 只要有活动就滚动视图
    if(interimTranscript || finalTranscript) {
        autoScrollView();
    }
}
    // ==========================================================
    // --- 界面控制与辅助函数 ---
    // ==========================================================

    controlBtn.addEventListener('click', async () => {
        if (isListening) {
            await endAndSummarizeSession();
        } else {
            try {
                const courseInput = await getCourseNameFromModal();
                currentCourseName = courseInput.trim() === "" ? "通用课程" : courseInput.trim();
                
                isListening = true;
                isPaused = false;
                
                initializeRecognition();
                
                let optimizationSuccess;
                showSpinner(`正在为 <strong>${currentCourseName}</strong> 课程优化识别引擎...`);
                try {
                    optimizationSuccess = await generateAndApplyGrammar(currentCourseName);
                } finally {
                    hideSpinner();
                }

                if (optimizationSuccess) {
                    liveContentOutput.innerHTML = `<p style="color: lightgreen; text-align: center;">优化完成！ <strong>${currentCourseName}</strong> 主题已明确。Here we go...</p>`;
                } else {
                    liveContentOutput.innerHTML = `<p style="color: orange; text-align: center;">优化失败，将使用标准识别模式。请开始说话...</p>`;
                }
                
                hasStarted = false; currentOriginalP = null; currentTranslationP = null;
                noteBuffer = ""; fullTranscriptHistory = "";
                classStartTime = new Date(); classCount++;
                startListening();

            } catch (error) {
                console.log("用户取消了开始课程。");
                isListening = false;
            }
        }
    });

    pauseBtn.addEventListener('click', () => {
        if (!isListening) return;

        if (!isPaused) {
            console.log("用户点击暂停。");
            isPaused = true;
            clearInactivityCountdown();
            if (recognition) recognition.stop();
            summarizeTextForNote(noteBuffer, currentCourseName);
            noteBuffer = "";
            pauseBtn.textContent = '继续';
            pauseBtn.classList.replace('pausable', 'resumable');
            updateStatusIndicator('paused');
        } else {
            console.log("用户点击继续。");
            isPaused = false;
            fullTranscriptHistory = "";
            initializeRecognition();
            startListening();
        }
    });

    async function endAndSummarizeSession() {
        console.log("用户结束课程。");
        isListening = false;
        isPaused = true;
        clearInactivityCountdown();
        if (recognition) recognition.stop();

        if (classStartTime) {
            await summarizeTextForNote(noteBuffer, currentCourseName);
            noteBuffer = "";
            const endTime = new Date();
            const durationSeconds = Math.round((endTime - classStartTime) / 1000);
            const minutes = Math.floor(durationSeconds / 60);
            const seconds = durationSeconds % 60;
            const summaryData = { title: `课堂 #${classCount}: ${currentCourseName}`, details: `结束时间: ${endTime.toLocaleString('zh-CN')}<br>持续时长: ${minutes}分 ${seconds}秒` };
            addNoteEntry(summaryData, 'session');
        }
        
        classStartTime = null;
        controlBtn.textContent = '开始上课';
        controlBtn.classList.remove('active');
        pauseBtn.disabled = true;
        pauseBtn.textContent = '暂停';
        pauseBtn.className = 'btn';
        liveContentOutput.classList.remove('listening');
        if (currentOriginalP) { currentOriginalP.remove(); currentOriginalP = null; }
        if (currentTranslationP) { currentTranslationP.remove(); currentTranslationP = null; }
        updateStatusIndicator('stopped');
        fullTranscriptHistory = "";
    }
    
    function showModeIndicator(text) {
        modeIndicator.textContent = text;
        modeIndicator.classList.add('show');
        setTimeout(() => { modeIndicator.classList.remove('show'); }, 1500);
    }

    function getCourseNameFromModal() {
        return new Promise((resolve, reject) => {
            courseNameModal.style.display = 'flex'; setTimeout(() => courseNameModal.classList.add('visible'), 10); courseNameInput.focus(); courseNameInput.value = currentCourseName === "通用课程" ? "" : currentCourseName;
            const handleConfirm = () => { cleanup(); resolve(courseNameInput.value); };
            const handleCancel = () => { cleanup(); reject(); };
            const handleKeydown = (event) => { if (event.key === 'Enter') handleConfirm(); else if (event.key === 'Escape') handleCancel(); };
            const cleanup = () => { courseNameModal.classList.remove('visible'); setTimeout(() => courseNameModal.style.display = 'none', 300); modalConfirmBtn.removeEventListener('click', handleConfirm); modalCancelBtn.removeEventListener('click', handleCancel); document.removeEventListener('keydown', handleKeydown); };
            modalConfirmBtn.addEventListener('click', handleConfirm); modalCancelBtn.addEventListener('click', handleCancel); document.addEventListener('keydown', handleKeydown);
        });
    }

    async function getWordDefinition(word) {
        const url = `https://api.dictionaryapi.dev/api/v2/entries/en/${word}`;
        try {
            const response = await fetch(url); if (!response.ok) return null; const data = await response.json(); const firstResult = data[0]; if (!firstResult) return null;
            const meaning = firstResult.meanings[0]; const definition = meaning?.definitions[0];
            const [translatedDef, translatedEx] = await Promise.all([ getFastTranslation(definition?.definition), getFastTranslation(definition?.example) ]);
            return { word: firstResult.word, phonetic: firstResult.phonetic || (firstResult.phonetics.find(p => p.text)?.text || ''), partOfSpeech: meaning?.partOfSpeech || 'N/A', definition_en: definition?.definition || '无定义。', example_en: definition?.example || '无例句。', definition_zh: translatedDef, example_zh: translatedEx, starred: false };
        } catch (error) { console.error("Dictionary API error:", error); return null; }
    }

    function autoScrollView() { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }
    
    function showPopupById(popupId) { document.querySelectorAll('.popup').forEach(p => p.classList.remove('visible')); const targetPopup = document.getElementById(popupId); if (targetPopup) { targetPopup.classList.add('visible'); } popupOverlay.classList.add('visible'); }
    
    function hideAllPopups() { popupOverlay.classList.remove('visible'); }
    
    function startInactivityCountdown() { clearInactivityCountdown(); warningTimer = setTimeout(() => { showPopupById('timeoutWarningPopup'); }, INACTIVITY_TIMEOUT - 10000); inactivityTimer = setTimeout(async () => { hideAllPopups(); await endAndSummarizeSession(); }, INACTIVITY_TIMEOUT); }
    
    function clearInactivityCountdown() { clearTimeout(warningTimer); clearTimeout(inactivityTimer); }
    
    function showDictionaryPopup(word, sentence) {
        const cleanedWord = word.replace(/[.,?!:;]$/, '').toLowerCase(); currentPopupData = { word: cleanedWord, contextSentence: sentence, definitionData: null }; popupContent.innerHTML = `<div class="loader"></div><p style="text-align:center;">正在查询 "${cleanedWord}"...</p>`; addVocabBtn.disabled = true; addVocabBtn.textContent = '添加单词本'; showPopupById('dictionaryPopup');
        getWordDefinition(cleanedWord).then(data => {
            if (data) {
                currentPopupData.definitionData = data; popupContent.innerHTML = `<div class="dict-entry"><div class="word-title">${data.word}</div><div class="word-phonetic">${data.phonetic}</div><div class="meaning-block"><p><strong>词性:</strong> ${data.partOfSpeech}</p><p><strong>英文释义:</strong> ${data.definition_en}</p><p><strong>中文释义:</strong> ${data.definition_zh}</p></div><div class="meaning-block"><p><strong>英文例句:</strong> <em>${data.example_en}</em></p><p><strong>中文翻译:</strong> <em>${data.example_zh}</em></p></div></div>`;
                if (vocabularyList.some(item => item.word === data.word)) { addVocabBtn.textContent = '已添加 ✔'; } else { addVocabBtn.disabled = false; }
            } else { popupContent.innerHTML = `<p>抱歉，找不到 “${cleanedWord}” 的标准定义。<br>请尝试AI上下文分析。</p>`; }
        });
    }

    async function getAIContextualExplanation(word, sentence) {
    aiPopupContent.innerHTML = `<div class="loader"></div><p style="text-align: center;">我正在全力分析，请稍等主人~\n"${word}"...</p>`; showPopupById('aiPopup');
    const prompt = `This is a university lecture on "${currentCourseName}". I encountered a word and need a brief explanation.\nThe sentence is: "${sentence}"\nThe word to understand is: "${word}"\n\nPlease answer strictly in the following format, without any extra explanations or introductory phrases:\n1.  **Contextual Meaning**: What does "${word}" most likely mean in this sentence? Please explain in Chinese.\n2.  **Extended Explanation**: Provide a broader explanation of the word, including other possible meanings, usage, or relevant cultural background (e.g., if it's an acronym, give the full name and explanation).\n3.  `;
    try {
        // 【修改点在这里】
        const response = await fetch(`${BACKEND_API_BASE_URL}/api/deepseek-chat`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, // 移除了 'Authorization'
            body: JSON.stringify({ model: 'deepseek-chat', messages: [{ role: 'user', content: prompt }], temperature: 0.3 }) 
        });
        
        if (!response.ok) throw new Error(`DeepSeek API error! status: ${response.status}`); 
        const data = await response.json();
        if (data.choices && data.choices.length > 0) { 
            const formattedResponse = data.choices[0].message.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>'); 
            aiPopupContent.innerHTML = `<div class="ai-definition">${formattedResponse}</div>`; 
        } else { 
            aiPopupContent.innerHTML = `<p>DeepSeek AI did not return a result.</p>`; 
        }
    } catch (error) { 
        console.error("DeepSeek AI fetch error (for context):", error); 
        aiPopupContent.innerHTML = `<p class="error-message">DeepSeek AI context analysis failed. Please check network or API Key.</p>`; 
    }
}

    
    function addNoteEntry(content, type = 'summary') {
        const defaultMessage = document.querySelector('#noteOutput .default-note-message'); if (defaultMessage) defaultMessage.remove(); const noteEntry = document.createElement('div'); noteEntry.className = 'note-entry'; let htmlContent = ''; const timestamp = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute:'2-digit' });
        if (type === 'summary') { const formattedContent = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>'); htmlContent = `<div class="note-header"><span>笔记摘要</span><span class="timestamp">${timestamp}</span></div><div class="note-content">${formattedContent}</div>`; } else if (type === 'session') { htmlContent = `<div class="note-header session-summary"><span>${content.title}</span><span class="timestamp">${timestamp}</span></div><div class="note-content">${content.details}</div>`; }
        noteEntry.innerHTML = `${htmlContent}<button class="delete-note-btn">删除</button>`; noteOutput.appendChild(noteEntry);
    }
    
    // --- 替换这个函数 ---

function updateStatusIndicator(state, message = '') {
    statusIndicator.style.display = state === 'stopped' ? 'none' : 'flex';
    waveIndicator.style.display = state === 'listening' ? 'flex' : 'none';
    
    const shouldShowPauseIcon = state === 'paused' || state === 'error';
    pauseIndicator.style.display = shouldShowPauseIcon ? 'flex' : 'none';

    if (shouldShowPauseIcon) {
        if (state === 'error') {
            // 错误状态显示警告符号
            pauseIndicator.innerHTML = '&#9888;'; // Warning sign
            pauseIndicator.title = message;
        } else {
            // ✅ 修改开始
            // 暂停状态显示新的自定义动画
            pauseIndicator.innerHTML = '<div class="custom-loader"></div>';
            pauseIndicator.title = '已暂停';
            // ✅ 修改结束
        }
    }
}
    
    function switchView(targetViewId) { views.forEach(view => { view.style.display = 'none'; }); document.getElementById(targetViewId).style.display = 'block'; [transBtn, noteBtn, vocabBtn].forEach(btn => btn.classList.remove('active-view')); const activeBtnMap = { 'translationView': transBtn, 'noteView': noteBtn, 'vocabView': vocabBtn }; if (activeBtnMap[targetViewId]) activeBtnMap[targetViewId].classList.add('active-view'); }
    
    function renderVocabList() {
        if (vocabularyList.length === 0) { vocabListContainer.innerHTML = `<p style="color: #a0a8b7;">你收藏的单词会出现在这里。</p>`; return; }
        vocabularyList.sort((a, b) => (b.starred ? 1 : 0) - (a.starred ? 1 : 0)); vocabListContainer.innerHTML = '';
        vocabularyList.forEach(item => { const card = document.createElement('div'); card.className = `vocab-card ${item.starred ? 'starred' : ''}`; card.innerHTML = `<div class="word">${item.word} <span class="phonetic">${item.phonetic}</span></div><div class="meaning"><strong>${item.partOfSpeech}:</strong> ${item.definition_zh || item.definition_en}<br><em>例: ${item.example_zh || item.example_en}</em></div><div class="vocab-card-actions"><button class="star-btn ${item.starred ? 'starred' : ''}" data-word="${item.word}">${item.starred ? '★ Unstar' : '☆ Star'}</button><button class="mastered-btn" data-word="${item.word}">已掌握</button></div>`; vocabListContainer.appendChild(card); });
    }

    // --- 事件监听器 ---
    modeSwitch.addEventListener('change', () => {
        isFullPowerMode = modeSwitch.checked;
        showModeIndicator(isFullPowerMode ? '满血模式' : '经济模式');
        if (isListening && !isPaused) { if(recognition) recognition.stop(); }
    });

    transBtn.addEventListener('click', () => switchView('translationView'));
    noteBtn.addEventListener('click', () => switchView('noteView'));
    vocabBtn.addEventListener('click', () => switchView('vocabView'));

    popupOverlay.addEventListener('click', (event) => { if (event.target === popupOverlay) { hideAllPopups(); } });
    
    aiContextSearchBtn.addEventListener('click', () => { if (currentPopupData.word && currentPopupData.contextSentence) { hideAllPopups(); setTimeout(() => { getAIContextualExplanation(currentPopupData.word, currentPopupData.contextSentence); }, 150); } });
    
    noteOutput.addEventListener('click', (event) => { if (event.target.classList.contains('delete-note-btn')) { const noteEntry = event.target.closest('.note-entry'); if (noteEntry) { noteEntry.style.transition = 'opacity 0.3s ease, transform 0.3s ease'; noteEntry.style.opacity = '0'; noteEntry.style.transform = 'scale(0.95)'; setTimeout(() => { noteEntry.remove(); if (noteOutput.children.length === 0) { noteOutput.innerHTML = `<p class="default-note-message">你的笔记将在这里显示。</p>`; } }, 300); } } });
    
    addVocabBtn.addEventListener('click', () => { if (!currentPopupData.definitionData || addVocabBtn.disabled) return; if (!vocabularyList.some(item => item.word === currentPopupData.definitionData.word)) { vocabularyList.push(currentPopupData.definitionData); renderVocabList(); } addVocabBtn.textContent = '已添加 ✔'; addVocabBtn.disabled = true; setTimeout(hideAllPopups, 800); });
    
    liveContentOutput.addEventListener('click', (event) => { const target = event.target; if (target.classList.contains('word')) { const word = target.textContent.trim(); const sentence = target.parentElement.textContent.trim(); showDictionaryPopup(word, sentence); } });
    
    vocabListContainer.addEventListener('click', (event) => { const target = event.target; const word = target.dataset.word; if (!word) return; if (target.classList.contains('mastered-btn')) { vocabularyList = vocabularyList.filter(item => item.word !== word); } else if (target.classList.contains('star-btn')) { const wordItem = vocabularyList.find(item => item.word === word); if (wordItem) wordItem.starred = !wordItem.starred; } renderVocabList(); });

    resumeBtn.addEventListener('click', () => { hideAllPopups(); if (isListening && isPaused) { pauseBtn.click(); } });

    endSessionBtn.addEventListener('click', async () => { hideAllPopups(); await endAndSummarizeSession(); });

    // --- 初始化 ---
    noteOutput.innerHTML = `<p class="default-note-message">你的课堂同传内容和笔记将在这里显示~</p>`;
    switchView('translationView');
    updateStatusIndicator('stopped');
    showModeIndicator('经济模式');
}