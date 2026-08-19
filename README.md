# Personal AI Image Editor 🎨✨

نظام شخصي واحترافي متكامل لتعديل الصور بالذكاء الاصطناعي مع الحفاظ الفائق على ملامح وهوية الشخص، يعمل محلياً من المتصفح على جهاز Windows، بينما يتم تشغيل موديل الاستدلال على GPU في **RunPod** فقط وقت الحاجة لتقليل التكلفة لأدنى حد.

---

## 🌟 أبرز المميزات (Key Features)

1. **حفاظ فائق على الهوية (Identity Preservation)**:
   - تثبيت ملامح الوجه، شكل العيون، الأنف، بنية الوجه، ولون البشرة مع إمكانية التعديل الشامل للملابس، الخلفية، الإضاءة، والوضعية.
2. **محرك أوامر ذكي محلي (Local Prompt Engine)**:
   - دعم كامل للغة العربية والإنجليزية.
   - تصنيف تلقائي للطلب (`OUTFIT`, `BACKGROUND`, `POSE`, `CAMERA`, `LIGHTING`, `OBJECT`, `HAIR`, `FACE`, `STYLE`).
   - تطبيق قاعدة **Preserve vs Change** بذكاء (عدم حفظ العنصر الذي طلب المستخدم تغييره، مع الحفاظ الصارم على باقي العناصر).
   - توليد Structured Professional Photography Prompts لضمان أعلى واقعية وجودة إخراج.
3. **طبقة استدلال معيارية (Modular Providers)**:
   - الموديل الأساسي: **FireRed-Image-Edit-1.1** (FireRedTeam).
   - الموديل الثاني الجاهز للإضافة: **Qwen-Image-Edit-2511**.
   - دعم **Local Mock Provider** للتجربة المجانية الفورية بدون استهلاك أي رصيد GPU.
4. **تعديل متسلسل بضغطة زر (Sequential Editing)**:
   - زر `Edit Again` لتمرير النتيجة فوراً كمدخل للتعديل التالي دون الحاجة لإعادة الرفع.
5. **مقارنة تفاعلية قبل وبعد (Interactive Before/After Slider)**:
   - سلايدر انزلاقي سلس ومقارنة جنباً إلى جنب (Side-by-Side).
6. **سجل محلي كامل (/history/)**:
   - حفظ الصور الأصلية والمعدلة مع كامل الـ Metadata والـ Seeds والأوامر محلياً على جهازك.
7. **إدارة التكلفة والإيقاف التلقائي (Cost Tracking & Auto-Stop)**:
   - عداد Uptime حي، وحساب تكلفة الـ GPU بالدولار.
   - مؤقت Auto-Stop لإيقاف الـ Pod تلقائياً عند الخمول لمنع نسيان الـ GPU يعمل.

---

## 📁 هيكل المشروع (Project Structure)

```text
personal-ai-image-editor/
├── local/                          # التطبيق والواجهة المحلية (Windows PC)
│   ├── css/style.css               # ثيم Dark Mode بتصميم Glassmorphism احترافي
│   ├── js/app.js                   # منطق التفاعل، السلايدر، السجل، والاتصال
│   ├── index.html                  # الواجهة الرئيسية
│   ├── prompt_engine.py            # محرك الـ Prompt الذكي المحلي (CPU)
│   ├── providers.py                # مزودات RunPod و Mock و RunPod API
│   ├── server.py                   # خادم FastAPI المحلي (http://127.0.0.1:7860)
│   ├── config.json                 # الإعدادات المحلية
│   └── requirements.txt            # متطلبات الخادم المحلي
│
├── runpod/                         # خادم الاستدلال على RunPod GPU Pod
│   ├── api.py                      # خادم FastAPI الاستدلالي (POST /edit, GET /health)
│   ├── inference.py                # مزودات FireRed و Qwen
│   ├── model_loader.py             # إدارة الـ VRAM والتخزين في /workspace
│   ├── image_utils.py              # معالجة وتصغير وتدوير الصور
│   ├── test_model.py               # حزمة اختبار الـ 20 حالة لـ Milestone 1
│   ├── requirements.txt            # متطلبات GPU و Diffusers
│   ├── install.sh                  # سكريبت تثبيت بضغطة زر
│   └── start.sh                    # سكريبت تشغيل السيرفر
│
├── shared/
│   └── schemas.py                  # نماذج البيانات المشتركة (Pydantic)
│
├── tests/                          # اختبارات الوحدة الآلية
│   ├── test_prompt_engine.py
│   ├── test_local_server.py
│   └── test_runpod_api.py
│
├── .env.example & .env             # متغيرات البيئة
├── .gitignore                      # حماية المفاتيح والسجلات
├── run_local.bat                   # تشغيل الواجهة بضغطة زر على Windows
├── run_local.py                    # مشغل Python للواجهة المحلية
└── README.md                       # دليل الاستخدام والتوثيق
```

---

## 🚀 دليل التشغيل السريع (Quick Start Guide)

### أولاً: التشغيل المحلي على جهاز Windows

1. **تثبيت المتطلبات المحلية**:
   ```bash
   pip install -r local/requirements.txt
   ```
2. **تشغيل البرنامج**:
   - إما بالضغط المزدوج على ملف `run_local.bat`
   - أو تشغيل الأمر:
     ```bash
     python run_local.py
     ```
3. سيفتح المتصفح تلقائياً على الرابط:
   ```text
   http://127.0.0.1:7860
   ```
4. البرنامج يبدأ تلقائياً في **Mock Mode** لتجربة الواجهة وتحليل الـ Prompts وحفظ السجل محلياً مجاناً.

---

### ثانياً: نشر خادم الاستدلال على RunPod Serverless

1. **إنشاء Serverless Endpoint على RunPod**:
   - اختر **A100 80GB أو H100 80GB**. لا تستخدم A40/A6000 48GB لهذا الموديل: أوزانه وحدها تستهلك قرابة 44GB ولا تترك مساحة آمنة للاستدلال.
   - عيّن **Container Disk = 80GB أو أكثر**، و **Max Workers = 1** و **Max Concurrency = 1**. النموذج يحتاج مساحة تنزيل وكاش فعلية، لا 20GB الافتراضية.
   - اترك `RUNPOD_CPU_OFFLOAD=0`. لا تفعّله إلا إذا كان الـendpoint مخصصًا له 64GB RAM على الأقل؛ هو أبطأ وقد يُقتل الـcontainer عند حد RAM أصغر.
2. **بناء الصورة ورفعها إلى Docker registry ثم ربطها بالـEndpoint**:
   ```bash
   # نفّذ من جذر المشروع، ثم استبدل registry/name بقيمة صورتك
   docker build -f runpod/Dockerfile -t <registry>/personal-ai-image-editor:serverless .
   docker push <registry>/personal-ai-image-editor:serverless
   ```
   - في RunPod Serverless اختر هذه الصورة، واضبط متغيرات البيئة الموجودة في Dockerfile كما هي، ثم اضغط **Deploy**.
3. **ربط الواجهة المحلية بالـEndpoint**:
   - انسخ **Endpoint ID** (وليس رابط Proxy).
   - افتح **الإعدادات (Settings)** في الواجهة المحلية، وضعه في حقل `RunPod Serverless Endpoint ID`، وأدخل RunPod API Key، وغيّر نوع المزود إلى **RunPod Serverless**.
   - اضغط **حفظ الإعدادات**. سيتحول المؤشر فوراً إلى: `● GPU Ready`.

---

## 🧪 اختبار الجودة الإلزامي (Milestone 1 Benchmark)

قبل البدء في الاستخدام اليومي، يمكنك تشغيل اختبار الـ 20 حالة المعتمدة في الخطة لتقييم جودة FireRed 1.1:

```bash
# داخل RunPod:
python runpod/test_model.py --image /path/to/test_portrait.jpg --output benchmark_results
```

يقوم السكريبت بتنفيذ الـ 20 اختباراً (تغيير ملابس، خلفيات متعددة، زوايا تصوير، وضعيات، إضاءات، عناصر، وتعديل متسلسل) وحفظ تقرير شامل في `benchmark_results/benchmark_report.json` وصور النتائج للمعاينة.

---

## ⚙️ التحكم في التكلفة (Cost Optimization)

- **Stop Pod**: أوقف الـ Pod من لوحة RunPod أو من زر `إيقاف الـ Pod` في إعدادات التطبيق بعد انتهاء جلسة العمل.
- **Auto-Stop**: يفحص النظام الخمول كل دقيقة، وإذا لم يتم توليد أي صورة خلال 30 دقيقة (قابلة للتعديل)، يرسل أمر إيقاف الـ Pod تلقائياً عبر RunPod API.

---

## 🔒 الأمان والخصوصية (Privacy & Security)

- جميع الصور وسجل التعديل تُحفظ **محلياً فقط** داخل مجلد `history/` على جهازك.
- لا يتم حفظ أي صور أو سجلات على RunPod؛ تُحذف الملفات المؤقتة فور انتهاء المعالجة.
- ملفات المفاتيح `.env` و `history/` محمية بالكامل في `.gitignore`.
