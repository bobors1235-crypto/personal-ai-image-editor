# خطة تنفيذ مشروع Personal AI Image Editor

مشروع **Personal AI Image Editor** هو نظام محلي متكامل واحترافي لتعديل
الصور بالذكاء الاصطناعي مع الحفاظ الدقيق على الهوية والملامح، يعمل عبر
واجهة ويب محلية فائقة السلاسة على Windows، مع تشغيل موديلات الـ GPU
المتطورة (**FireRed-Image-Edit-1.1** و **Qwen-Image-Edit-2511**) على
**RunPod** عند الحاجة فقط لتقليل التكلفة لأدنى حد.

------------------------------------------------------------------------

## 1. المعمارية المعتمدة (System Architecture)

    ┌─────────────────────────────────────────────────────────────┐
    │                    Windows PC (Local)                       │
    │                                                             │
    │  ┌───────────────────────┐       ┌───────────────────────┐  │
    │  │   Modern Web UI       │ <---> │   Local FastAPI Host  │  │
    │  │ (HTML5/CSS3/JS/Theme) │       │   (local/server.py)   │  │
    │  └───────────────────────┘       └───────────┬───────────┘  │
    │                                              │              │
    │       ┌──────────────────────────────────────┴──────────┐   │
    │       │ Local Features:                                 │   │
    │       │ • /history/ Local Image & Metadata Store        │   │
    │       │ • GPU Uptime & Live Cost Calculator             │   │
    │       │ • Auto-Stop Idle Timer & RunPod API Controls    │   │
    │       │ • InferenceProvider Interface (RunPod / Mock)   │   │
    │       └─────────────────────────────────────────────────┘   │
    └───────────────────────────────┬─────────────────────────────┘
                                    │ HTTPS / REST API
                                    ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                     RunPod GPU Pod                          │
    │                                                             │
    │  ┌───────────────────────────────────────────────────────┐  │
    │  │ FastAPI Inference Server (runpod/api.py)              │  │
    │  ├───────────────────────────────────────────────────────┤  │
    │  │ • Receives Enhanced Prompt from Local Prompt Engine   │  │
    │  │ • Model Loader & Memory Manager (Warm VRAM / Cache)   │  │
    │  │ • Modular Providers:                                  │  │
    │  │    ├── FireRedProvider (FireRed-Image-Edit-1.1)       │  │
    │  │    └── QwenProvider (Qwen-Image-Edit-2511)            │  │
    │  │ • Image Processor (Resizing, EXIF, Temporary Cleanup) │  │
    │  └───────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────┘

------------------------------------------------------------------------

## 2. تفاصيل المكونات والملفات (Proposed Components)

### أ. الطبقة المشتركة (Shared Layer)

-   **`shared/schemas.py`**:
    -   `EditRequest`: بيانات الطلب (الصورة بصيغة base64/binary، الـ
        prompt، seed، quality، identity_strength، model_name).
    -   `EditResponse`: الناتج (الصورة المعدلة، seed، زمن المعالجة،
        enhanced_prompt، metadata).
    -   `HealthResponse`: حالة الـ Pod والـ GPU (status، vram_used،
        vram_total، active_model، gpu_name).
    -   `PromptAnalysis`: تصنيف الأوامر (change tags, preserve tags,
        structured prompt).
    -   `HistoryItem`: تخزين بيانات الجلسة وسجل التعديل محلياً.
    -   `ConfigSchema`: إعدادات البرنامج والـ RunPod.

------------------------------------------------------------------------

### ب. خادم الاستدلال على RunPod (`runpod/`)

> **مبدأ مهم:** محرك تحسين وتحليل الـ Prompt يعمل محلياً على جهاز Windows
> وليس على GPU في RunPod في الإصدار الأول. RunPod مسؤول أساساً عن تحميل
> موديل الصور وتنفيذ الـ inference. هذا يقلل التعقيد والتكلفة ويتيح
> تحليل الـ Prompt حتى عندما يكون الـ Pod متوقفاً.

1.  **`runpod/model_loader.py` & `runpod/inference.py`**:
    -   واجهة `InferenceProvider` الموحدة.
    -   `FireRedProvider`: تحميل وتشغيل
        `FireRedTeam/FireRed-Image-Edit-1.1` مع دعم `bfloat16`، إدارة
        كاش الـ VRAM، وتثبيت الـ Seed.
    -   `QwenProvider`: يُضاف بعد اختبار واعتماد/رفض FireRed؛ لا يلزم
        تنفيذه في أول Milestone.
    -   إدارة الذاكرة وتخزين **ملفات الموديل والكاش** في `/workspace`
        حتى لا يلزم تنزيلها من الإنترنت في كل جلسة.
    -   ملاحظة: عند Stop/Restart للـ Pod يجب تحميل الموديل من القرص إلى
        VRAM مرة أخرى؛ الـ VRAM نفسها لا تبقى محفوظة بعد إيقاف الـ GPU.
2.  **`runpod/image_utils.py`**:
    -   معالجة أبعاد الصور مع الحفاظ على Aspect Ratio والحد الأقصى
        للأبعاد.
    -   تصحيح تدوير EXIF.
    -   حذف الملفات المؤقتة فور إرسال النتيجة للحفاظ على الخصوصية
        والمساحة.
3.  **`runpod/api.py`**:
    -   `POST /edit`: استقبال الصورة والـ Enhanced Prompt وتنفيذ التعديل
        وإرجاع النتيجة.
    -   `GET /health`: فحص حالة الـ GPU والـ VRAM والموديل المحمل.
    -   `POST /model/load`: تبديل الموديل الفعال برمجياً عند إضافة أكثر
        من Provider.
4.  **`runpod/install.sh` & `runpod/start.sh` &
    `runpod/requirements.txt`**:
    -   سكريبتات إعداد وتشغيل بضغطة زر داخل RunPod.

------------------------------------------------------------------------

### ج. التطبيق والواجهة المحلية (`local/`)

1.  **`local/server.py`**:

    -   خادم FastAPI محلي يعمل على `http://127.0.0.1:7860`.
    -   طبقة `Provider` المحلية التي تتصل بـ RunPod أو تعمل بـ
        `MockProvider` للتجربة والتطوير بدون GPU.
    -   فحص الـ Health الدوري ومراقبة Uptime وحساب التكلفة التقديرية
        الحية (\$ / hour).
    -   مؤقت الإيقاف التلقائي (**Auto Stop**) عند خمول النظام لمنع
        استهلاك الرصيد.
    -   دعم أوامر Start / Stop للـ Pod عبر RunPod API عند تنفيذ هذه
        الميزة.
    -   إدارة السجل المحلي (`/history/`) وحفظ الصور والـ Metadata
        تلقائياً.

2.  **`local/prompt_engine.py` (محرك الـ Prompt الذكي المحلي)**:

    -   يعمل على CPU محلياً ولا يحتاج GPU أو LLM ضخم في الإصدار الأول.
    -   دعم العربية والإنجليزية باستخدام Rules + Templates واضحة وقابلة
        للاختبار.
    -   تصنيف التعديل (`OUTFIT`, `BACKGROUND`, `POSE`, `CAMERA`,
        `LIGHTING`, `OBJECT`, `HAIR`, `FACE`, `STYLE`, `GENERAL`).
    -   تطبيق قاعدة **Preserve vs Change** بحيث لا يطلب من الموديل تثبيت
        العنصر الذي طلب المستخدم تغييره.
    -   إنشاء Structured Professional Editing Prompt مناسب للموديل.
    -   تطبيق Identity Preservation Rules حسب `High / Normal / Low`.
    -   Endpoint محلي اختياري `/prompt/analyze` لمعاينة التحليل والـ
        Enhanced Prompt بدون تشغيل RunPod.

3.  **`local/index.html` & `local/css/style.css` & `local/js/app.js`**:

4.  **`local/index.html` & `local/css/style.css` & `local/js/app.js`**:

    -   واجهة Dark Mode حديثة جداً واحترافية (Glassmorphism & Crisp
        Typography).
    -   منطقة رفع الصور مع دعم Drag & Drop و Paste من الحافظة
        (Clipboard) والمعاينة الفورية.
    -   حقل إدخال Prompt ذكي مع اقتراحات جاهزة للأنماط وتحديد اللغة
        التلقائي.
    -   خيارات التحكم:
        -   اختيار الموديل (FireRed 1.1 / Qwen 2511).
        -   درجة الحفاظ على الهوية (Identity Preservation: High / Normal
            / Low).
        -   جودة الإخراج ومستوى الدقة (Output Quality: High / Normal).
        -   التحكم في الـ Seed (عشوائي أو رقم مخصص).
        -   إمكانية تفعيل المقارنة (Compare Models).
    -   عرض النتائج:
        -   مقارنة قبل وبعد تفاعلية (Before / After Split Slider &
            Side-by-Side View).
        -   زر **Edit Again** لتمرير الناتج مباشرة كمدخل للتعديل التالي
            (Sequential Editing).
        -   أزرار التنزيل وحفظ السجل.
    -   **Developer Mode Drawer**:
        -   عرض الـ Prompt الأصلي والموسع (Enhanced Prompt).
        -   تصنيف التغييرات والاحتفاظات (Preserve vs Change).
        -   استهلاك VRAM وزمن التوليد بالثواني.
    -   شريط حالة RunPod (مؤشر الاتصال، وقت التشغيل، التكلفة المقدرة، زر
        Reconnect، زر Auto-Stop).
    -   معرض السجل المحلي (History Drawer) لاستعراض واستعادة التعديلات
        السابقة.

------------------------------------------------------------------------

### د. ملفات التكوين والتشغيل في بيئة العمل

-   **`.env.example`** و **`.env`**
-   **`.gitignore`** (حماية المفاتيح والسجلات والمجلدات المؤقتة)
-   **`local/config.json`** (الإعدادات المحلية الافتراضية)
-   **`run_local.bat`** و **`run_local.py`** (تشغيل الواجهة المحلية
    بضغطة زر على Windows)
-   **`README.md`** (دليل شامل باللغتين العربية والإنجليزية لطريقة
    التثبيت، التشغيل على RunPod، والتعديل)

### سياسة RunPod والتخزين لتقليل التكلفة

-   الاستخدام الأساسي: **Start Pod → Load Model to VRAM → Edit Session →
    Stop Pod**.
-   استخدم **Stop** بدل Terminate عندما تعتمد على تخزين `/workspace`
    المرتبط بالـ Pod.
-   ملفات الموديل تبقى على التخزين الدائم، لكن الموديل يحتاج Reload إلى
    VRAM بعد كل تشغيل جديد.
-   إذا أصبح المطلوب مستقبلاً Terminate وإنشاء Pod جديد بحرية، يتم تقييم
    استخدام Network Volume.
-   سعر الساعة في `config.json` يكون قابلاً للتعديل ولا يتم Hard-code
    لسعر GPU ثابت لأن أسعار RunPod والتوفر تتغير.

------------------------------------------------------------------------

## 3. بوابة الجودة الإلزامية قبل بناء التطبيق الكامل (Mandatory Quality Gate)

> \[!IMPORTANT\] **لا يبدأ بناء الواجهة النهائية أو الخصائص الثانوية قبل
> اعتماد جودة الموديل عملياً.** نجاح المشروع يعتمد أولاً على جودة الـ
> Image Editing وليس على شكل الـ UI.

### Milestone 1 --- Model Quality Test

1.  تشغيل **FireRed-Image-Edit-1.1 فقط في البداية** على RunPod باستخدام
    GPU مناسب بذاكرة 48GB مثل RTX A6000 أو A40 حسب الأرخص والمتاح.
2.  إنشاء Minimal Inference Script أو `/edit` API فقط، بدون بناء الواجهة
    النهائية.
3.  اختبار ما لا يقل عن **20 حالة فعلية** بصور يحددها المستخدم، تشمل:
    -   تغيير الملابس.
    -   تغيير الخلفية بالكامل.
    -   تغيير الـ Pose.
    -   تغيير زاوية الكاميرا.
    -   تغيير الإضاءة.
    -   إضافة وإزالة عناصر.
    -   أوامر متعددة في Prompt واحد.
    -   الحفاظ على الهوية والوجه.
    -   Sequential Editing على نتيجة سابقة.
4.  لكل اختبار يتم حفظ:
    -   Original Image
    -   Result Image
    -   Original Prompt
    -   Enhanced Prompt
    -   Seed
    -   Model Settings
    -   Generation Time
5.  تقييم النتائج بصرياً، مع إعطاء الأولوية لـ:
    1.  Prompt Following
    2.  Identity Preservation
    3.  Photorealism
    4.  Anatomy / Hands / Face
    5.  Consistency after major pose/camera changes

### Go / No-Go

-   **GO:** إذا اعتمد المستخدم جودة FireRed، نكمل بناء الـ API والواجهة
    والـ History وCost Controls.
-   **NO-GO / MODEL TEST:** إذا FireRed أقل من الجودة المطلوبة، يتم
    اختبار **Qwen-Image-Edit-2511** على نفس مجموعة الاختبارات قبل
    استكمال التطبيق.
-   لا يتم تحميل FireRed وQwen معاً في VRAM في الإصدار الأول.
-   `Compare Models` ميزة لاحقة فقط بعد اعتماد النظام الأساسي، لأنها
    تزيد وقت وتكلفة التوليد.

> لا يوجد ضمان تقني أن تغيير Pose أو Camera Angle جذري سيحافظ على الوجه
> بنسبة 100%. المطلوب هو قياس الجودة عملياً على صور الاستخدام الحقيقية
> قبل استثمار وقت التطوير في بقية المنتج.

------------------------------------------------------------------------

## 4. خطة التحقق والاختبار (Verification Plan)

### أ. الاختبارات الآلية (Automated Tests)

1.  **اختبار محرك الـ Prompt (`test_prompt_engine.py`)**:
    -   فحص تصنيف الأوامر العربية والإنجليزية (تغيير ملابس، خلفية،
        وضعية، إضاءة، عناصر).
    -   التأكد من صحة منطق Preserve vs Change (عدم الحفاظ على ما طُلب
        تغييره).
2.  **اختبار خادم الاستدلال (`test_runpod_api.py`)**:
    -   فحص نقاط `/health` و `/edit` و `/prompt/analyze` في بيئة Mock.
3.  **اختبار الخادم المحلي (`test_local_server.py`)**:
    -   فحص مسارات الواجهة، حفظ السجل في `/history/`، حساب التكلفة،
        وإرسال الطلبات للـ Provider.

### ب. التحقق البصري والوظيفي

-   تشغيل الخادم المحلي وفتح `http://127.0.0.1:7860` للتأكد من استجابة
    الواجهة، دعم السحب والإفلات، التعديل المتسلسل (Edit Again)، وسجل
    التاريخ.
-   التحقق من دعم العربية والانجليزية في الـ UI ومحرك الـ Prompt.

------------------------------------------------------------------------

> \[!IMPORTANT\] يرجى مراجعة الخطة وإعطاء الموافقة للبدء الفوري في
> التنفيذ البرمجي بكافة التفاصيل.
