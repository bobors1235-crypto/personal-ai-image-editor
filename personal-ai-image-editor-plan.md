# Personal AI Image Editor --- Developer Implementation Plan

## 1. الهدف

بناء **Local AI Image Editor** للاستخدام الشخصي يعمل من المتصفح على جهاز
Windows، بينما يتم تشغيل موديل تعديل الصور على GPU في RunPod فقط وقت
الحاجة لتقليل التكلفة.

المستخدم يرفع صورة ويكتب أمرًا طبيعيًا بالعربية أو الإنجليزية، مثل:

> غير اللبس لبدلة سودا وخلي التصوير في شارع في نيويورك بالليل.

أو:

> Change the camera angle to a low-angle cinematic shot, keep the same
> person and face, and change the outfit to a black leather jacket.

### المطلوب من النظام

-   الحفاظ على هوية وملامح الشخص قدر الإمكان.
-   تنفيذ الـ Prompt بدقة.
-   تغيير الملابس.
-   تغيير الخلفية والمشهد.
-   تغيير الإضاءة.
-   تغيير زاوية التصوير.
-   تغيير الـ Pose قدر الإمكان.
-   إضافة أو إزالة عناصر.
-   الحفاظ على Photorealism.
-   دعم تعديلات متتابعة على نفس الصورة.

------------------------------------------------------------------------

## 2. الموديل الأساسي

ابدأ باختبار:

**FireRed-Image-Edit-1.1**

ويجب تصميم الـ Backend بطريقة Modular حتى يمكن تبديل الموديل لاحقًا بدون
إعادة بناء البرنامج.

الموديل الثاني الذي نريد إمكانية إضافته لاحقًا:

**Qwen-Image-Edit-2511**

### قاعدة أساسية

ممنوع ربط التطبيق بموديل واحد Hard-coded.

استخدم Interface / Provider Layer مثل:

``` text
InferenceProvider
    ├── FireRedProvider
    └── QwenProvider
```

------------------------------------------------------------------------

## 3. RunPod GPU Strategy

الهدف هو **أقل تكلفة ممكنة** مع VRAM كافية.

ابدأ بالبحث عن:

1.  RTX A6000 48GB Community Cloud
2.  A40 48GB Community Cloud
3.  RTX A6000 48GB Secure Cloud
4.  A40 48GB Secure Cloud

اختيار الـ GPU يتم حسب الأرخص والمتاح وقت التشغيل.

لا نبدأ بـ H100 أو A100 إلا إذا أثبتت الاختبارات أن هناك حاجة فعلية.

### طريقة الاستخدام

في Version 1 نستخدم **RunPod Pod عادي**.

-   تشغيل الـ Pod فقط عند الحاجة.
-   إيقافه فور الانتهاء.
-   عدم ترك GPU يعمل 24/7.
-   الاحتفاظ بالموديل والملفات الضرورية في Persistent Storage.

استخدم:

``` text
/workspace
```

للموديلات والكاش والملفات التي يجب الاحتفاظ بها بين الجلسات.

------------------------------------------------------------------------

## 4. Architecture

``` text
Windows PC
│
├── Local HTML UI
├── CSS
├── JavaScript
└── Local FastAPI
        │
        │ HTTPS
        ▼
RunPod GPU
│
├── FastAPI Inference Server
├── Model Loader
├── FireRed Image Edit 1.1
├── Prompt Processor
└── Image Processor
        │
        ▼
Edited Image
        │
        ▼
Local Browser
```

لا يوجد Cloud Hosting للواجهة.

مثال:

``` text
http://127.0.0.1:7860
```

------------------------------------------------------------------------

## 5. GitHub

GitHub account:

``` text
bobors1235-crypto
```

اسم Repository مقترح:

``` text
personal-ai-image-editor
```

### Project Structure

``` text
personal-ai-image-editor/

├── local/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   ├── server.py
│   └── config.json
│
├── runpod/
│   ├── api.py
│   ├── inference.py
│   ├── model_loader.py
│   ├── prompt_engine.py
│   ├── image_utils.py
│   ├── requirements.txt
│   ├── install.sh
│   └── start.sh
│
├── shared/
│   └── schemas.py
│
├── .env.example
├── .gitignore
└── README.md
```

### Security

ممنوع رفع أي من التالي إلى GitHub:

-   RunPod API Key
-   Hugging Face tokens
-   Secrets
-   Private endpoints
-   Passwords

استخدم:

``` text
.env
```

ويجب إضافته إلى:

``` text
.gitignore
```

------------------------------------------------------------------------

## 6. Local UI

لا نستخدم ComfyUI كواجهة للمستخدم.

المطلوب واجهة بسيطة ونظيفة:

``` text
┌─────────────────────────────────────────────┐
│              AI IMAGE EDITOR                │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │            Upload Image               │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Describe your edit                         │
│  ┌───────────────────────────────────────┐  │
│  │ غير لبسه وخليه واقف في فندق...       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Model                                      │
│  [ FireRed Image Edit 1.1 ▼ ]              │
│                                             │
│  Identity Preservation   [ High ▼ ]         │
│  Output Quality          [ High ▼ ]         │
│                                             │
│              [ GENERATE ]                   │
│                                             │
│      BEFORE                  AFTER          │
│    [ image ]                [ image ]        │
│                                             │
│  [Edit Again] [Download] [New Image]        │
└─────────────────────────────────────────────┘
```

------------------------------------------------------------------------

## 7. Upload

دعم Drag & Drop والرفع العادي.

الصيغ:

-   JPG
-   JPEG
-   PNG
-   WEBP

يجب عرض Preview قبل إرسال الصورة.

------------------------------------------------------------------------

## 8. Sequential Editing

بعد كل Generation يوجد زر:

``` text
Edit Again
```

عند الضغط عليه تصبح الصورة الناتجة هي Input للتعديل التالي.

مثال:

### Edit 1

``` text
غير القميص لجاكيت جلد
```

### Edit 2

``` text
خلي الخلفية في باريس
```

### Edit 3

``` text
خلي التصوير Low Angle
```

بدون إعادة رفع الصورة يدويًا.

------------------------------------------------------------------------

## 9. Prompt Engine

هذه من أهم أجزاء المشروع.

لا يتم إرسال كلام المستخدم الخام للموديل دائمًا.

أنشئ:

``` python
enhance_edit_prompt()
```

### مثال

User Prompt:

``` text
غير اللبس لبدلة سودا
```

يمكن تحويله داخليًا إلى:

``` text
Replace the subject's current clothing with a tailored black suit.

Preserve:
- exact facial identity
- facial proportions
- hairstyle
- skin tone
- apparent age
- body proportions

Maintain photorealism and natural anatomy.

The clothing must fit the person's body naturally.
Preserve realistic fabric folds, lighting, shadows and reflections.

Do not unnecessarily modify the face, hands or background.
```

------------------------------------------------------------------------

## 10. Prompt Classification

الـ Prompt Processor يجب أن يصنف المطلوب إلى أنواع مثل:

``` text
OUTFIT
BACKGROUND
POSE
CAMERA
LIGHTING
OBJECT
HAIR
FACE
STYLE
GENERAL
```

وبناءً على النوع يضيف التعليمات المناسبة.

------------------------------------------------------------------------

## 11. Preserve vs Change Logic

هذه قاعدة أساسية.

لا نضيف تعليمات الحفاظ على شيء طلب المستخدم تغييره.

مثال:

``` text
غير وضعية التصوير وخليه قاعد
```

لا يجوز أن نضيف:

``` text
preserve exact pose
```

يجب أن يحول Prompt Engine الطلب إلى شيء منطقي مثل:

``` json
{
  "change": [
    "pose",
    "camera_angle"
  ],
  "preserve": [
    "identity",
    "face",
    "hair",
    "clothing",
    "environment"
  ]
}
```

هذا المنطق مهم جدًا لتحسين Prompt Following.

------------------------------------------------------------------------

## 12. Identity Preservation

عند وجود شخص في الصورة، تتم إضافة تعليمات الحفاظ على الهوية تلقائيًا ما
لم يطلب المستخدم تغيير شيء محدد.

مثال:

``` text
Preserve the exact identity of the person.
Do not unnecessarily change facial structure.
Keep recognizable facial features.
Maintain realistic skin texture.
```

إذا طلب المستخدم تغيير الشعر مثلًا، لا يتم الحفاظ على الشعر.

------------------------------------------------------------------------

## 13. Arabic Prompt Support

المستخدم يجب أن يستطيع الكتابة بالعربية أو الإنجليزية.

مثال:

``` text
خليه واقف على البحر وقت الغروب ولبسه قميص أبيض
```

يمكن تحويله داخليًا إلى Structured Prompt مثل:

``` text
ACTION:
Change clothing and environment.

SUBJECT:
Preserve exact identity, facial features, hairstyle and body proportions.

CLOTHING:
Natural fitted white linen shirt.

ENVIRONMENT:
Beach at sunset.

LIGHT:
Warm golden-hour sunlight consistent with the new environment.

COMPOSITION:
Integrate the person naturally into the scene.

QUALITY:
Photorealistic professional photography.
Natural skin texture.
Realistic shadows and fabric.
```

------------------------------------------------------------------------

## 14. Prompt Enhancer Cost

Version 1 لا يحتاج LLM إضافيًا ضخمًا على RunPod.

ابدأ بـ:

**Python Rules + Templates**

لأنها:

-   مجانية.
-   سريعة.
-   لا تستهلك VRAM إضافية.
-   سهلة التحكم.

لاحقًا يمكن إضافة LLM صغير إذا أثبتت الاختبارات أن هناك فائدة حقيقية.

------------------------------------------------------------------------

## 15. RunPod API

Endpoint أساسي:

``` http
POST /edit
```

Input تقريبي:

``` json
{
  "image": "...",
  "prompt": "...",
  "seed": 12345,
  "quality": "high",
  "identity_strength": "high"
}
```

Response تقريبي:

``` json
{
  "success": true,
  "image": "...",
  "seed": 12345,
  "processing_time": 8.21
}
```

للصور الكبيرة يفضل File Response أو Temporary URL بدل Base64 عندما يكون
ذلك عمليًا.

------------------------------------------------------------------------

## 16. Health Endpoint

``` http
GET /health
```

مثال:

``` json
{
  "status": "ready",
  "model": "FireRed-Image-Edit-1.1",
  "gpu": "RTX A6000",
  "vram_used": "...",
  "vram_total": "..."
}
```

الواجهة تعرض:

``` text
● GPU Ready
```

أو:

``` text
○ RunPod Offline
```

------------------------------------------------------------------------

## 17. Offline Handling

لأن RunPod لن يعمل 24/7، يجب أن تتعامل الواجهة مع Offline State بشكل
طبيعي.

مثال:

``` text
RunPod is offline.
Start your GPU Pod, then press Reconnect.
```

زر:

``` text
[ Reconnect ]
```

يعيد فحص:

``` text
/health
```

ولا يجب أن تنهار الواجهة إذا كان RunPod متوقفًا.

------------------------------------------------------------------------

## 18. Start / Stop RunPod

### Version 1

يتم تشغيل وإيقاف Pod يدويًا من RunPod Dashboard.

هذا أبسط وأأمن أثناء التطوير.

### Version 2

يمكن إضافة:

``` text
[ START GPU ]
[ STOP GPU ]
```

باستخدام RunPod API.

------------------------------------------------------------------------

## 19. Cost Controls

أضف في الواجهة:

``` text
GPU uptime: 00:37:21
Estimated GPU cost: $0.21
```

يتم حساب Estimated Cost من سعر الساعة الموجود في Local Config.

مثال:

``` json
{
  "gpu_hourly_cost": 0.33
}
```

------------------------------------------------------------------------

## 20. Auto Shutdown

ميزة مهمة لمنع نسيان GPU يعمل.

خيارات:

``` text
AUTO STOP: ON/OFF

15 min
30 min
60 min
Never
```

إذا لم يحدث Generation خلال المدة المحددة، يمكن للبرنامج المحلي إيقاف
الـ Pod باستخدام RunPod API بعد إضافة هذه الخاصية.

ابدأ بـ 30 دقيقة كخيار افتراضي عند تنفيذ الميزة.

------------------------------------------------------------------------

## 21. Resolution

Version 1:

``` text
Normal
High
```

لا نبدأ بـ Native 4K Diffusion بدون داعٍ.

نستخدم Resolution مناسبة للموديل ثم Upscaling اختياري.

------------------------------------------------------------------------

## 22. Upscaling

Upscaling لا يعمل تلقائيًا.

أضف زر:

``` text
[ Upscale Result ]
```

وبالتالي لا ندفع وقت GPU إضافيًا إلا عند الحاجة.

------------------------------------------------------------------------

## 23. Seed Control

دعم:

``` text
Seed: Random
```

مع إمكانية تثبيت Seed:

``` text
Seed: 38721491
```

للمساعدة في إعادة التجارب والـ Variations.

------------------------------------------------------------------------

## 24. Local History

كل الـ History تحفظ محليًا على جهاز المستخدم وليس RunPod.

مثال:

``` text
/history/
```

لكل Generation نحفظ Metadata مثل:

``` text
original image
result image
user prompt
enhanced prompt
seed
model
date
generation time
```

------------------------------------------------------------------------

## 25. Temporary Files & Privacy

RunPod يحتاج الصورة أثناء المعالجة فقط.

بعد انتهاء الـ Generation:

-   حذف Temporary Input.
-   حذف Temporary Output بعد إرساله بنجاح عند الإمكان.
-   عدم بناء Cloud Gallery.
-   عدم الاحتفاظ بتاريخ الصور على RunPod.

النسخ التي يريد المستخدم الاحتفاظ بها تحفظ محليًا.

------------------------------------------------------------------------

## 26. Developer Mode

أضف Developer Mode اختياري.

عند تفعيله يظهر:

``` text
Original Prompt
Enhanced Prompt
Seed
Steps
Guidance
Model
Resolution
Generation Time
VRAM Usage
```

هذا مهم جدًا أثناء اختبار الموديلات والـ Prompt Engine.

------------------------------------------------------------------------

## 27. Compare Models

بعد إضافة Qwen، يمكن إضافة:

``` text
Compare Models: ON/OFF
```

عند تشغيله يتم إرسال نفس الصورة ونفس الـ Prompt إلى:

``` text
FireRed
Qwen
```

ثم عرض:

``` text
FireRed Result | Qwen Result
```

يكون OFF افتراضيًا لأنه يزيد تكلفة الـ GPU.

------------------------------------------------------------------------

## 28. أشياء لا نحتاجها في Version 1

لا تضيع وقت التطوير حاليًا في:

-   Login System
-   User Accounts
-   Payment System
-   Cloud Frontend
-   Database Server
-   Admin Panel
-   Mobile App
-   Kubernetes
-   Multiple Workers
-   Complex Docker Orchestration
-   ComfyUI Frontend

المستخدم شخص واحد.

الأولوية:

``` text
Image
↓
Prompt
↓
Generate
↓
High Quality Result
```

------------------------------------------------------------------------

# مراحل التنفيذ

## Phase 1 --- Model Test

قبل بناء UI كامل:

شغل FireRed Image Edit 1.1 على A6000 48GB أو A40 48GB.

اختبر 10--20 صورة على الأقل في:

-   Outfit Change
-   Background Change
-   Camera Angle Change
-   Pose Change
-   Lighting
-   Object Replacement
-   Multiple Simultaneous Edits
-   Identity Preservation
-   Sequential Editing

### قرار Go / No-Go

إذا الجودة ليست قريبة من المستوى المطلوب، اختبر Qwen قبل استكمال الـ UI.

لا نبني التطبيق كاملًا حول موديل لم يتم اختبار جودته أولًا.

------------------------------------------------------------------------

## Phase 2 --- GPU API

بناء:

``` text
FastAPI
/model load
/edit
/health
```

يظل الموديل Loaded في VRAM أثناء جلسة تشغيل الـ Pod لتقليل وقت كل
Generation.

------------------------------------------------------------------------

## Phase 3 --- Local UI

تنفيذ:

-   Upload
-   Drag & Drop
-   Prompt
-   Generate
-   Loading / Progress State
-   Before / After
-   Edit Again
-   Download
-   New Image
-   History

------------------------------------------------------------------------

## Phase 4 --- Prompt Engine

إضافة:

-   Arabic Support
-   Prompt Classification
-   Preserve / Change Logic
-   Professional Prompt Expansion
-   Identity Preservation Rules

------------------------------------------------------------------------

## Phase 5 --- Cost Controls

إضافة:

-   GPU Uptime
-   Estimated Cost
-   Offline Detection
-   Reconnect
-   Auto Stop
-   Manual Stop

------------------------------------------------------------------------

## Phase 6 --- Second Model

بعد نجاح FireRed:

أضف:

``` text
Qwen-Image-Edit-2511
```

عن طريق Provider جديد بدون تغيير الـ Frontend.

------------------------------------------------------------------------

# RunPod Deployment Preference

ابدأ بالترتيب:

``` text
1. RTX A6000 48GB Community Cloud
2. A40 48GB Community Cloud
3. RTX A6000 48GB Secure Cloud
4. A40 48GB Secure Cloud
```

اختيار الأرخص المتاح وقت التشغيل.

لا نستخدم GPU أغلى إلا إذا كانت هناك فائدة مثبتة في:

-   Generation Speed
-   Model Compatibility
-   VRAM
-   Image Quality workflow

------------------------------------------------------------------------

# Cost Philosophy

المشروع مصمم للاستخدام الشخصي المتقطع.

لذلك:

``` text
Need editing
    ↓
Start RunPod
    ↓
Load model
    ↓
Edit images
    ↓
Finish session
    ↓
STOP RUNPOD
```

الهدف الأساسي هو عدم دفع تكلفة GPU أثناء عدم الاستخدام.

يجب حساب التكلفة الفعلية حسب سعر الـ GPU الظاهر في RunPod وقت التشغيل
لأن الأسعار والتوفر قد تتغير.

------------------------------------------------------------------------

# Future Serverless Option

لا نبدأ بـ Serverless.

بعد استقرار التطبيق، نقارن التكلفة الفعلية.

إذا أصبح نمط الاستخدام:

``` text
فتح التطبيق
↓
تعديل صورة أو صورتين
↓
إغلاقه
↓
العودة بعد عدة ساعات
```

يمكن دراسة نقل Inference إلى RunPod Serverless / Scale-to-Zero إذا كان
ذلك أوفر فعليًا بعد احتساب Cold Start ووقت تحميل الموديل.

------------------------------------------------------------------------

# أهم Architectural Requirement

الـ Frontend لا يجب أن يعرف تفاصيل الموديل أو RunPod.

استخدم:

``` text
Local UI
    ↓
Local API
    ↓
InferenceProvider
    ↓
RunPodProvider
```

لاحقًا يمكن إضافة:

``` text
RunPodProvider
LocalGPUProvider
OtherCloudProvider
```

بدون إعادة كتابة الواجهة.

------------------------------------------------------------------------

# MVP Definition

أول Version يعتبر ناجحًا عندما يعمل المسار التالي بثبات:

``` text
Local HTML
↓
Upload Image
↓
Arabic / English Prompt
↓
Automatic Prompt Enhancement
↓
Send to RunPod
↓
FireRed Image Edit
↓
Preserve Identity
↓
Return High Quality Edited Image
↓
Edit Result Again
↓
Save Locally
```

------------------------------------------------------------------------

# الأولويات

بالترتيب:

1.  **Image Quality**
2.  **Prompt Following**
3.  **Identity Preservation**
4.  **Low GPU Cost**
5.  **Reliability**
6.  **Simple Local UI**
7.  **Generation Speed**

لا نضحي بجودة الصورة من أجل إضافة Features غير ضرورية.

------------------------------------------------------------------------

# تعليمات أخيرة للديفلوبر

-   اختبر الموديل قبل بناء التطبيق كاملًا.
-   اجعل Model Layer قابلة للاستبدال.
-   لا تضع Secrets داخل GitHub.
-   لا تستخدم GPU غالي بدون سبب.
-   احتفظ بالموديلات في Persistent Storage.
-   تعامل مع RunPod Offline كحالة طبيعية.
-   لا تجعل Upscaling إلزاميًا.
-   احتفظ بالـ History محليًا.
-   اجعل Prompt Engine يفهم ما الذي يريد المستخدم تغييره وما الذي يريد
    الحفاظ عليه.
-   صمم المشروع للاستخدام الشخصي وليس SaaS.
-   الأولوية القصوى هي جودة تنفيذ التعديل وليس عدد الخصائص.
