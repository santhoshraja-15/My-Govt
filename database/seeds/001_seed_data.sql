-- ================================================================
-- MyGovt Seed Data — Tamil Nadu State, Districts, Departments,
-- Complaint Categories, SLA Rules, Schemes (30+), Services (20+)
-- Run after schema.sql
-- ================================================================

-- ── Source registry ───────────────────────────────────────────
INSERT INTO system.source_registry (source_id, source_code, source_name, source_type, url, jurisdiction, reliability_score, license, status)
VALUES
  (gen_random_uuid(), 'TN_GOV_PORTAL',    'Tamil Nadu Government Portal',         'government_portal', 'https://www.tn.gov.in',              'Tamil Nadu', 1.00, 'government_open',  'active'),
  (gen_random_uuid(), 'TNRD',             'Tamil Nadu Rural Development',          'government_portal', 'https://www.tnrd.gov.in',            'Tamil Nadu', 1.00, 'government_open',  'active'),
  (gen_random_uuid(), 'TN_WELFARE',       'TN Social Welfare & Women Empowerment', 'government_portal', 'https://www.socialwelfare.tn.gov.in','Tamil Nadu', 1.00, 'government_open',  'active'),
  (gen_random_uuid(), 'TN_AGRI',          'TN Department of Agriculture',          'government_portal', 'https://www.tnau.ac.in',             'Tamil Nadu', 1.00, 'government_open',  'active'),
  (gen_random_uuid(), 'TN_EDUC',          'TN School Education Department',        'government_portal', 'https://www.tnschools.gov.in',       'Tamil Nadu', 1.00, 'government_open',  'active'),
  (gen_random_uuid(), 'TN_HEALTH',        'TN Health & Family Welfare',            'government_portal', 'https://www.tnhealth.tn.gov.in',     'Tamil Nadu', 1.00, 'government_open',  'active'),
  (gen_random_uuid(), 'TN_REVENUE',       'TN Revenue Department (e-Sevai)',       'government_portal', 'https://www.esevai.gov.in',          'Tamil Nadu', 1.00, 'government_open',  'active')
ON CONFLICT DO NOTHING;

-- ── State ──────────────────────────────────────────────────────
INSERT INTO administration.state (state_id, state_code, state_name, state_name_ta)
VALUES (1, 'TN', 'Tamil Nadu', 'தமிழ்நாடு')
ON CONFLICT DO NOTHING;

-- ── Districts (all 38 districts of Tamil Nadu) ─────────────────
INSERT INTO administration.district (district_id, state_id, district_code, district_name, district_name_ta, headquarters) VALUES
  (1,  1,'TN-CHE','Chennai',      'சென்னை',       'Chennai'),
  (2,  1,'TN-COI','Coimbatore',   'கோயம்புத்தூர்', 'Coimbatore'),
  (3,  1,'TN-MAD','Madurai',      'மதுரை',         'Madurai'),
  (4,  1,'TN-TRI','Tiruchirappalli','திருச்சிராப்பள்ளி','Tiruchirappalli'),
  (5,  1,'TN-SAL','Salem',        'சேலம்',         'Salem'),
  (6,  1,'TN-TIR','Tirunelveli',  'திருநெல்வேலி',  'Tirunelveli'),
  (7,  1,'TN-VEL','Vellore',      'வேலூர்',        'Vellore'),
  (8,  1,'TN-EDE','Erode',        'ஈரோடு',         'Erode'),
  (9,  1,'TN-THA','Thane',        'தஞ்சாவூர்',     'Thanjavur'),
  (10, 1,'TN-DIN','Dindigul',     'திண்டுக்கல்',   'Dindigul'),
  (11, 1,'TN-KAN','Kancheepuram', 'காஞ்சிபுரம்',   'Kancheepuram'),
  (12, 1,'TN-TKR','Thiruvallur',  'திருவள்ளூர்',   'Thiruvallur'),
  (13, 1,'TN-CUD','Cuddalore',    'கடலூர்',        'Cuddalore'),
  (14, 1,'TN-VIL','Villupuram',   'விழுப்புரம்',   'Villupuram'),
  (15, 1,'TN-NAG','Nagapattinam', 'நாகப்பட்டினம்', 'Nagapattinam'),
  (16, 1,'TN-THI','Thiruvarur',   'திருவாரூர்',    'Thiruvarur'),
  (17, 1,'TN-PUD','Pudukkottai',  'புதுக்கோட்டை',  'Pudukkottai'),
  (18, 1,'TN-SIV','Sivaganga',    'சிவகங்கை',      'Sivaganga'),
  (19, 1,'TN-RAM','Ramanathapuram','ராமநாதபுரம்',  'Ramanathapuram'),
  (20, 1,'TN-TUT','Thoothukudi',  'தூத்துக்குடி',  'Thoothukudi'),
  (21, 1,'TN-KAN','Kanniyakumari', 'கன்னியாகுமரி', 'Nagercoil'),
  (22, 1,'TN-VIR','Virudhunagar', 'விருதுநகர்',    'Virudhunagar'),
  (23, 1,'TN-THE','Theni',        'தேனி',           'Theni'),
  (24, 1,'TN-KRI','Krishnagiri',  'கிருஷ்ணகிரி',   'Krishnagiri'),
  (25, 1,'TN-DHE','Dharmapuri',   'தர்மபுரி',      'Dharmapuri'),
  (26, 1,'TN-TIV','Tiruvannamalai','திருவண்ணாமலை', 'Tiruvannamalai'),
  (27, 1,'TN-NMK','Namakkal',     'நாமக்கல்',      'Namakkal'),
  (28, 1,'TN-KAR','Karur',        'கரூர்',          'Karur'),
  (29, 1,'TN-ARI','Ariyalur',     'அரியலூர்',      'Ariyalur'),
  (30, 1,'TN-PER','Perambalur',   'பெரம்பலூர்',    'Perambalur'),
  (31, 1,'TN-TIV','Tirupur',      'திருப்பூர்',    'Tirupur'),
  (32, 1,'TN-NID','Nilgiris',     'நீலகிரி',        'Udhagamandalam'),
  (33, 1,'TN-MAY','Mayiladuthurai','மயிலாடுதுறை',  'Mayiladuthurai'),
  (34, 1,'TN-CAL','Kallakurichi', 'கள்ளக்குறிச்சி','Kallakurichi'),
  (35, 1,'TN-TEN','Tenkasi',      'தென்காசி',      'Tenkasi'),
  (36, 1,'TN-CHE','Chengalpattu', 'செங்கல்பட்டு',  'Chengalpattu'),
  (37, 1,'TN-RAN','Ranipet',      'ராணிப்பேட்டை',  'Ranipet'),
  (38, 1,'TN-TIR','Tirupattur',   'திருப்பத்தூர்', 'Tirupattur')
ON CONFLICT DO NOTHING;

-- ── Departments (15 key departments) ──────────────────────────
INSERT INTO administration.department (department_id, department_code, department_name, department_name_ta, short_name, portal_url, status) VALUES
  (1,  'REVT',  'Revenue Department',                    'வருவாய் துறை',               'Revenue',   'https://www.tnrevenue.gov.in',       'active'),
  (2,  'HLTH',  'Health and Family Welfare',              'சுகாதாரம் மற்றும் குடும்ப நலத்துறை','Health','https://www.tnhealth.tn.gov.in','active'),
  (3,  'EDUC',  'School Education Department',            'பள்ளிக் கல்வி துறை',         'Education', 'https://www.tnschools.gov.in',       'active'),
  (4,  'AGRI',  'Department of Agriculture',              'வேளாண்மை துறை',              'Agriculture','https://www.agri.tn.gov.in',        'active'),
  (5,  'SWWF',  'Social Welfare and Women Empowerment',   'சமூக நலன் மற்றும் மகளிர் உரிமையாண்மை','SocialWelfare','https://www.socialwelfare.tn.gov.in','active'),
  (6,  'HRCE',  'Hindu Religious and Charitable Endowments','இந்து அறநிலையம் துறை',   'HR&CE',     'https://www.tnhrce.gov.in',          'active'),
  (7,  'MAWS',  'Municipal Administration and Water Supply','நகராட்சி மேலாண்மை',      'Municipal', 'https://www.tnmaws.tn.gov.in',       'active'),
  (8,  'RDPR',  'Rural Development and Panchayati Raj',   'கிராம வளர்ச்சி துறை',        'RuralDev',  'https://www.tnrd.gov.in',            'active'),
  (9,  'LABO',  'Labour Welfare Department',              'தொழிலாளர் நலத்துறை',         'Labour',    'https://www.labour.tn.gov.in',       'active'),
  (10, 'HOUS',  'Housing and Urban Development',          'வீடு மற்றும் நகர்ப்புற வளர்ச்சி','Housing','https://www.tnhb.gov.in',          'active'),
  (11, 'FISH',  'Fisheries and Fishermen Welfare',        'மீன்வளம் மற்றும் மீனவர் நலன்','Fisheries','https://www.fisheries.tn.gov.in',  'active'),
  (12, 'FORE',  'Environment, Forests and Climate Change','சுற்றுச்சூழல் மற்றும் காடுகள்','Forests', 'https://www.forests.tn.gov.in',      'active'),
  (13, 'ELEC',  'Electricity Department (TANGEDCO)',      'மின்சார துறை',               'Electricity','https://www.tangedco.gov.in',       'active'),
  (14, 'HHSS',  'Highways Department',                   'நெடுஞ்சாலைத் துறை',           'Highways',  'https://www.highways.tn.gov.in',     'active'),
  (15, 'SCHE',  'Adi Dravidar Welfare Department',       'ஆதிதிராவிட நலத்துறை',         'AdiDravidar','https://www.adidravidar.gov.in',    'active')
ON CONFLICT DO NOTHING;

-- ── Complaint categories with SLA rules ───────────────────────
INSERT INTO complaints.complaint_category (category_id, department_id, name, name_ta, description, default_priority, is_active) VALUES
  (gen_random_uuid(), 13, 'Power Outage / Electricity Fault',   'மின்தடை',              'Power supply interruption or fault',        'high',   true),
  (gen_random_uuid(),  7, 'Water Supply Disruption',             'குடிநீர் பிரச்சனை',    'Drinking water supply issue',              'high',   true),
  (gen_random_uuid(),  7, 'Road Damage / Potholes',              'சாலை சேதம்',           'Road or pothole repair needed',             'medium', true),
  (gen_random_uuid(),  7, 'Garbage / Waste Collection',          'குப்பை',               'Waste collection or dump complaint',        'medium', true),
  (gen_random_uuid(),  2, 'Hospital / Medical Services',         'மருத்துவமனை',          'Public hospital or health centre complaint','high',   true),
  (gen_random_uuid(),  3, 'School Infrastructure',               'பள்ளி',                'School building, facilities, staff',        'medium', true),
  (gen_random_uuid(),  1, 'Certificate / Document Delay',        'சான்றிதழ் தாமதம்',    'Revenue certificate delay at e-Sevai',      'medium', true),
  (gen_random_uuid(),  8, 'Panchayat / Rural Issue',             'பஞ்சாயத்து பிரச்சனை', 'Rural road, drainage, or panchayat',        'medium', true),
  (gen_random_uuid(),  4, 'Agricultural Support',                'வேளாண் உதவி',          'Seeds, loans, subsidy not received',        'medium', true),
  (gen_random_uuid(),  5, 'Social Welfare Benefit Delay',        'சமூக நலன் தாமதம்',    'Pension, scheme benefit not credited',      'high',   true);

-- ── SLA rules for complaint categories ───────────────────────
INSERT INTO complaints.sla_rule (category_id, priority, resolution_hours, escalation_hours, escalation_authority_level, is_active)
SELECT cc.category_id, 'high',   24,  12, 2, true FROM complaints.complaint_category cc WHERE cc.default_priority = 'high'
UNION ALL
SELECT cc.category_id, 'medium', 72,  48, 1, true FROM complaints.complaint_category cc WHERE cc.default_priority = 'medium'
ON CONFLICT DO NOTHING;

-- ── Schemes (30 real Tamil Nadu government schemes) ────────────
INSERT INTO schemes.scheme (scheme_id, scheme_code, name, name_ta, description, department_id,
  scheme_level, category, status, effective_from, verified_at, application_url, official_source_url, source_id)
SELECT
  gen_random_uuid(),
  s.code, s.name, s.name_ta, s.description, s.dept_id,
  'state', s.category, 'active', '2024-01-01',
  now(), s.app_url, s.src_url,
  (SELECT source_id FROM system.source_registry LIMIT 1)
FROM (VALUES
  ('TN-CM-BREAKFAST',  'Chief Minister Breakfast Scheme',
   'முதல்வர் காலை உணவு திட்டம்',
   'Free nutritious breakfast for government school students from Class 1 to 5.',
   3, 'education', 'https://www.tnschools.gov.in', 'https://www.tnschools.gov.in'),
  ('TN-AMMA-UNAVAGAM', 'Amma Unavagam (Subsidised Canteen)',
   'அம்மா உணவகம்',
   'Subsidised meals at Rs.1 for idli and Rs.5 for full meals at government canteens.',
   7, 'food_nutrition', 'https://www.tn.gov.in', 'https://www.tn.gov.in'),
  ('TN-KALAIGNAR-MAGALIR-URIMAI',
   'Kalaignar Magalir Urimai Thogai',
   'கலைஞர் மகளிர் உரிமை தொகை',
   'Rs.1000 per month financial assistance to eligible women who are heads of households.',
   5, 'women_welfare', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-AMMA-BABY-CARE',
   'Amma Baby Care Kit',
   'அம்மா குழந்தை பராமரிப்பு கிட்',
   'Baby care kit provided to mothers who deliver in government hospitals.',
   2, 'health_maternal', 'https://www.tnhealth.tn.gov.in', 'https://www.tnhealth.tn.gov.in'),
  ('TN-CM-HEALTH-INS',
   'Chief Minister Comprehensive Health Insurance',
   'முதல்வர் விரிவான சுகாதார காப்பீடு',
   'Health insurance coverage up to Rs.5 lakh per family for BPL and income up to Rs.72,000 annually.',
   2, 'health_insurance', 'https://www.cmchistn.com', 'https://www.cmchistn.com'),
  ('TN-PATTA-CHITTA',
   'Patta Chitta (Land Records)',
   'பட்டா சிட்டா',
   'Online access to land ownership records (Patta) and field map (Chitta) for all citizens.',
   1, 'land_records', 'https://eservices.tn.gov.in', 'https://eservices.tn.gov.in'),
  ('TN-THALIKKU-THANGAM',
   'Thalikku Thangam Scheme',
   'தாலிக்கு தங்கம்',
   '8 grams gold coin for Thali (marriage symbol) for brides in BPL families at government weddings.',
   5, 'women_welfare', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-MOOVALUR-RAMAMIRTHAM',
   'Moovalur Ramamirtham Ammaiyar Higher Education Scheme',
   'மூவலூர் இராமாமிர்தம் அம்மையார் உயர்கல்வி திட்டம்',
   'Rs.1000/month stipend for first-generation women graduates from BPL families pursuing higher education.',
   5, 'education', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-NIRP-PENSION',
   'Old Age Pension (IGNOAPS)',
   'வயதானோர் ஓய்வூதியம்',
   'Rs.1000/month pension under Indira Gandhi National Old Age Pension Scheme for citizens above 60 years from BPL families.',
   5, 'social_security', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-WIDOW-PENSION',
   'Widow Pension Scheme',
   'விதவை ஓய்வூதியம்',
   'Rs.1000/month financial assistance to widows below poverty line.',
   5, 'social_security', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-DISABILITY-PENSION',
   'Disability Pension Scheme',
   'மாற்றுத்திறனாளி ஓய்வூதியம்',
   'Rs.1000/month to persons with 40% or more permanent disability from BPL families.',
   5, 'social_security', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-KUDUMBASREE',
   'Pudhu Vaazhvu / Self-Help Group Scheme',
   'புதுவாழ்வு சுய உதவி குழு',
   'Financial linkage, training and livelihood support for women self-help groups in rural Tamil Nadu.',
   8, 'livelihood', 'https://www.tnrd.gov.in', 'https://www.tnrd.gov.in'),
  ('TN-PM-KISAN',
   'PM-Kisan (Pradhan Mantri Kisan Samman Nidhi)',
   'பிரதம மந்திரி கிசான் சம்மான் நிதி',
   'Rs.6000/year (3 installments) direct income support to farmer families owning cultivable land.',
   4, 'agriculture', 'https://www.pmkisan.gov.in', 'https://www.pmkisan.gov.in'),
  ('TN-AGRI-LOAN-WAIVER',
   'Agricultural Loan Waiver Scheme (TN)',
   'வேளாண் கடன் தள்ளுபடி திட்டம்',
   'One-time waiver of short-term crop loans up to Rs.1 lakh for farmers in Tamil Nadu.',
   4, 'agriculture', 'https://www.agri.tn.gov.in', 'https://www.agri.tn.gov.in'),
  ('TN-FREE-SEEDS',
   'Free Seed Distribution',
   'இலவச விதை விநியோகம்',
   'Distribution of certified seeds to small and marginal farmers at no cost by the Agriculture Department.',
   4, 'agriculture', 'https://www.agri.tn.gov.in', 'https://www.agri.tn.gov.in'),
  ('TN-AMMA-TWO-WHEELER',
   'Amma Two Wheeler Scheme',
   'அம்மா இரு சக்கர வாகன திட்டம்',
   '50% subsidy (max Rs.25,000) on two-wheelers for college-going girls from government/aided colleges.',
   5, 'women_education', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-LAPTOP-SCHEME',
   'Free Laptop Scheme for Students',
   'மாணவர்களுக்கு இலவச மடிக்கணினி',
   'Free laptops provided to Class 11 and college students in government and government-aided schools.',
   3, 'education', 'https://www.tnschools.gov.in', 'https://www.tnschools.gov.in'),
  ('TN-UZHAVAR-SANDHAI',
   'Uzhavar Sandhai (Farmers Market)',
   'உழவர் சந்தை',
   'Direct-to-consumer vegetable markets where farmers sell produce without middlemen at fair prices.',
   4, 'agriculture', 'https://www.agri.tn.gov.in', 'https://www.agri.tn.gov.in'),
  ('TN-FISHERMEN-INSURANCE',
   'Fishermen Group Personal Accident Insurance',
   'மீனவர் குழு விபத்து காப்பீடு',
   'Rs.5 lakh accident insurance cover for marine fishermen and Rs.1.5 lakh accidental death cover.',
   11, 'fisheries', 'https://www.fisheries.tn.gov.in', 'https://www.fisheries.tn.gov.in'),
  ('TN-MAKKALAI-THEDI',
   'Makkalai Thedi Maruthuvam (Doorstep Healthcare)',
   'மக்களை தேடி மருத்துவம்',
   'Free doorstep healthcare screening for chronic diseases for citizens above 35 years.',
   2, 'health_doorstep', 'https://www.tnhealth.tn.gov.in', 'https://www.tnhealth.tn.gov.in'),
  ('TN-FREE-BUS-PASS',
   'Free Bus Pass for Women',
   'பெண்களுக்கு இலவச பஸ் பாஸ்',
   'Free travel in Tamil Nadu government buses for all women in the state.',
   5, 'transport', 'https://www.tn.gov.in', 'https://www.tn.gov.in'),
  ('TN-CONSTRUCTION-WORKER-WELFARE',
   'Construction Worker Welfare Scheme (BOCW)',
   'கட்டுமான தொழிலாளர் நலத் திட்டம்',
   'Welfare benefits including housing, scholarship, marriage assistance for registered construction workers.',
   9, 'labour_welfare', 'https://www.labour.tn.gov.in', 'https://www.labour.tn.gov.in'),
  ('TN-NEET-COACHING',
   'Free NEET Coaching (Arasamaram)',
   'இலவச நீட் பயிற்சி',
   'Free NEET coaching for government school students from rural Tamil Nadu to enter medical colleges.',
   3, 'education', 'https://www.tnschools.gov.in', 'https://www.tnschools.gov.in'),
  ('TN-ENNAI-THOTTU',
   'Ennai Thottu Adi Kaapom (Child Safety Scheme)',
   'என்னை தொட்டு அடி காப்போம்',
   'Child protection scheme providing support and counselling for abused or trafficked children.',
   5, 'child_welfare', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-HUTS-SCHEME',
   'Adi Dravidar Housing Scheme',
   'ஆதிதிராவிட வீடுகள் திட்டம்',
   'Pucca houses for Scheduled Castes and Scheduled Tribe families under state welfare programme.',
   15, 'housing', 'https://www.adidravidar.gov.in', 'https://www.adidravidar.gov.in'),
  ('TN-ANAITHU-GRAMA-ANNA',
   'Anaithu Grama Anna Marumalarchi Yojana',
   'அனைத்து கிராம அண்ணா மறுமலர்ச்சி யோஜனா',
   'Integrated rural development scheme covering 12 activities for all Tamil Nadu villages.',
   8, 'rural_development', 'https://www.tnrd.gov.in', 'https://www.tnrd.gov.in'),
  ('TN-SOLAR-PUMP',
   'Free Solar Pump for Farmers',
   'விவசாயிகளுக்கு இலவச சோலார் பம்ப்',
   'Free solar-powered pump sets for small and marginal farmers for irrigation.',
   4, 'agriculture', 'https://www.agri.tn.gov.in', 'https://www.agri.tn.gov.in'),
  ('TN-UNEMPLOYED-YOUTH',
   'Unemployed Youth Financial Support (UYFS)',
   'வேலையில்லாத இளைஞர் நிதி உதவி',
   'Monthly stipend of Rs.1000 for two years for unemployed youth who have completed degree education.',
   9, 'youth_employment', 'https://www.labour.tn.gov.in', 'https://www.labour.tn.gov.in'),
  ('TN-TRANSGEND-WELFARE',
   'Tamil Nadu Transgender Welfare Board Schemes',
   'திருநங்கை நல வாரியம் திட்டங்கள்',
   'Housing, livelihood, healthcare, education and legal support for transgender persons in TN.',
   5, 'transgender_welfare', 'https://www.socialwelfare.tn.gov.in', 'https://www.socialwelfare.tn.gov.in'),
  ('TN-NLEP-LEPROSY',
   'National Leprosy Eradication Programme (TN)',
   'தேசிய தொழுநோய் ஒழிப்பு திட்டம்',
   'Free treatment, rehabilitation and stigma-free care for leprosy-affected persons in Tamil Nadu.',
   2, 'health_leprosy', 'https://www.tnhealth.tn.gov.in', 'https://www.tnhealth.tn.gov.in')
) AS s(code, name, name_ta, description, dept_id, category, app_url, src_url)
ON CONFLICT DO NOTHING;

-- ── Eligibility rules for key schemes ─────────────────────────
-- Kalaignar Magalir Urimai (Women head of household + income)
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'gender', '=', '"female"', NULL, true,
  'Applicant must be female', 'விண்ணப்பதாரர் பெண்ணாக இருக்க வேண்டும்',
  'GO Ms No. 1, Social Welfare, 2023'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-KALAIGNAR-MAGALIR-URIMAI'
UNION ALL
SELECT gen_random_uuid(), s.scheme_id, 1, 'annual_income', '<=', '100000', 'INR', true,
  'Annual family income must be ≤ Rs.1,00,000', 'குடும்ப வருமானம் ₹1,00,000-க்கு கீழ் இருக்க வேண்டும்',
  'GO Ms No. 1, Social Welfare, 2023'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-KALAIGNAR-MAGALIR-URIMAI'
ON CONFLICT DO NOTHING;

-- Old Age Pension (age >= 60 AND BPL)
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'age', '>=', '60', 'years', true,
  'Age must be 60 years or above', 'வயது 60 வயதுக்கு மேல் இருக்க வேண்டும்',
  'IGNOAPS Guidelines, Ministry of Rural Development'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-NIRP-PENSION'
UNION ALL
SELECT gen_random_uuid(), s.scheme_id, 1, 'bpl_status', 'IS_TRUE', 'true', NULL, true,
  'Must belong to Below Poverty Line (BPL) family', 'வறுமை கோட்டிற்கு கீழ் (BPL) குடும்பத்தில் இருக்க வேண்டும்',
  'IGNOAPS Guidelines, Ministry of Rural Development'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-NIRP-PENSION'
ON CONFLICT DO NOTHING;

-- Disability Pension
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'disability_status', 'IS_TRUE', 'true', NULL, true,
  'Must have 40% or more permanent disability', 'நிரந்தர ஊனம் 40% அல்லது அதிகமாக இருக்க வேண்டும்',
  'PWD Act, Social Welfare GO'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-DISABILITY-PENSION'
UNION ALL
SELECT gen_random_uuid(), s.scheme_id, 1, 'bpl_status', 'IS_TRUE', 'true', NULL, true,
  'Must belong to BPL family', 'BPL குடும்பத்தில் இருக்க வேண்டும்',
  'PWD Act, Social Welfare GO'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-DISABILITY-PENSION'
ON CONFLICT DO NOTHING;

-- CM Health Insurance (income <= 72000 OR bpl)
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'annual_income', '<=', '72000', 'INR', true,
  'Annual family income must be ≤ Rs.72,000', 'குடும்ப வருடாந்திர வருமானம் ₹72,000-க்கு கீழ் இருக்க வேண்டும்',
  'CMCHIS GO 2009'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-CM-HEALTH-INS'
UNION ALL
SELECT gen_random_uuid(), s.scheme_id, 2, 'bpl_status', 'IS_TRUE', 'true', NULL, true,
  'OR must belong to BPL family', 'அல்லது BPL குடும்பத்தில் இருக்க வேண்டும்',
  'CMCHIS GO 2009'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-CM-HEALTH-INS'
ON CONFLICT DO NOTHING;

-- Amma Two Wheeler Scheme
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'gender', '=', '"female"', NULL, true,
  'Applicant must be female', 'விண்ணப்பதாரர் பெண்ணாக இருக்க வேண்டும்',
  'Social Welfare GO 2023'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-AMMA-TWO-WHEELER'
UNION ALL
SELECT gen_random_uuid(), s.scheme_id, 1, 'is_student', 'IS_TRUE', 'true', NULL, true,
  'Must be enrolled in government or aided college', 'அரசு அல்லது அரசு உதவி பெறும் கல்லூரி மாணவியாக இருக்க வேண்டும்',
  'Social Welfare GO 2023'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-AMMA-TWO-WHEELER'
ON CONFLICT DO NOTHING;

-- PM-Kisan
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'occupation', 'IN', '["farmer","cultivator","agricultural laborer"]', NULL, true,
  'Applicant or family must be a farmer/cultivator', 'விண்ணப்பதாரர் விவசாயி / உழவராக இருக்க வேண்டும்',
  'PM-Kisan Scheme Guidelines 2019'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-PM-KISAN'
ON CONFLICT DO NOTHING;

-- Unemployed Youth Financial Support
INSERT INTO schemes.eligibility_rule (rule_id, scheme_id, rule_group, attribute, operator, value, unit, mandatory, human_readable, human_readable_ta, source_reference)
SELECT gen_random_uuid(), s.scheme_id, 1, 'age', 'BETWEEN', '[21, 35]', 'years', true,
  'Age must be between 21 and 35 years', 'வயது 21 முதல் 35 வரை இருக்க வேண்டும்',
  'Labour Welfare GO 2023'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-UNEMPLOYED-YOUTH'
UNION ALL
SELECT gen_random_uuid(), s.scheme_id, 1, 'education_level', 'IN', '["graduate","postgraduate"]', NULL, true,
  'Must have completed a degree (graduate or above)', 'பட்டப்படிப்பு முடித்திருக்க வேண்டும்',
  'Labour Welfare GO 2023'
FROM schemes.scheme s WHERE s.scheme_code = 'TN-UNEMPLOYED-YOUTH'
ON CONFLICT DO NOTHING;

-- ── Services (20 key e-Sevai services) ────────────────────────
INSERT INTO services.service (service_id, service_code, name, name_ta, description, department_id,
  category, government_fee, service_charge, processing_days, status, application_url, official_source_url)
VALUES
  (gen_random_uuid(),'SVC-NATIVITY',   'Nativity Certificate',              'சொந்த ஊர் சான்றிதழ்','Proof of birth district issued by Revenue',1,'certificate',50,20,7,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-COMM-CERT',  'Community Certificate',             'சமுதாய சான்றிதழ்','Caste/community certificate for SC/ST/OBC/OC',1,'certificate',50,20,7,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-INCOME-CERT','Income Certificate',                'வருமான சான்றிதழ்', 'Annual income certificate from VAO/Tahsildar', 1,'certificate',50,20,7,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-RESID-CERT', 'Residence Certificate',             'வாசிப்பிட சான்றிதழ்','Proof of residence address',                1,'certificate',50,20,7,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-BIRTH-CERT', 'Birth Certificate',                 'பிறப்பு சான்றிதழ்','Official birth certificate',                 7,'certificate',50,20,3,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-DEATH-CERT', 'Death Certificate',                 'இறப்பு சான்றிதழ்', 'Official death certificate',                 7,'certificate',50,20,3,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-MARRIAGE',   'Marriage Certificate',              'திருமண சான்றிதழ்', 'Registration of marriage under HMA/SMA',     1,'certificate',100,20,15,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-PATTA',      'Patta Chitta (Land Record)',        'பட்டா சிட்டா',     'Land ownership record (patta) or field map', 1,'land_record', 50,20,3,'active','https://eservices.tn.gov.in','https://eservices.tn.gov.in'),
  (gen_random_uuid(),'SVC-ENCUMB',     'Encumbrance Certificate',           'இடையூறு சான்றிதழ்','EC for land transactions from sub-registrar',1,'land_record',100,20,3,'active','https://eservices.tn.gov.in','https://eservices.tn.gov.in'),
  (gen_random_uuid(),'SVC-RATION',     'Ration Card Application',           'ரேஷன் அட்டை',      'Apply for new or modify existing ration card',1,'welfare',   0,  20,30,'active','https://esevai.gov.in','https://www.tnpds.gov.in'),
  (gen_random_uuid(),'SVC-DISABILITY', 'Disability Certificate',            'மாற்றுத்திறன் சான்றிதழ்','Medical certificate for disability',   2,'certificate', 0,  20,14,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-SENIOR',     'Senior Citizen Certificate',        'மூத்த குடிமக்கள் சான்றிதழ்','Certificate for persons above 60 years',1,'certificate',0, 20,7,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-FARMER-ID',  'Farmer Identity Card',              'விவசாயி அடையாள அட்டை','Official farmer ID from Agriculture Dept', 4,'agriculture',0,  0, 30,'active','https://agri.tn.gov.in','https://agri.tn.gov.in'),
  (gen_random_uuid(),'SVC-KIOSK',      'e-Sevai Centre Locator',            'இ-சேவை மையம் கண்டுபிடிப்பு','Find nearest Common Service Centre',  7,'locator',    0,   0,0,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-DRIVING',    'Learner Licence Application',       'ஓட்டுனர் உரிமம் விண்ணப்பம்','Apply for learner driving licence',  1,'transport',  200,20,7,'active','https://parivahan.gov.in','https://parivahan.gov.in'),
  (gen_random_uuid(),'SVC-TNPSC-OBC', 'OBC / MBC Certificate for TNPSC',   'TNPSC OBC சான்றிதழ்','Other Backward Classes certificate for TNPSC',1,'certificate',50,20,7,'active','https://esevai.gov.in','https://esevai.gov.in'),
  (gen_random_uuid(),'SVC-PENSION-APP','Old Age Pension Application',       'முதியோர் ஓய்வூதியம் விண்ணப்பம்','Apply for IGNOAPS pension',    5,'welfare',    0, 20,30,'active','https://socialwelfare.tn.gov.in','https://socialwelfare.tn.gov.in'),
  (gen_random_uuid(),'SVC-WATER-CONN', 'Water Supply New Connection',       'புதிய குடிநீர் இணைப்பு','Apply for new water supply connection',  7,'utilities', 500,200,30,'active','https://www.chennaimetrowater.tn.gov.in','https://www.tnmaws.tn.gov.in'),
  (gen_random_uuid(),'SVC-ELECT-CONN', 'Electricity New Connection (LT)',   'மின்சார புதிய இணைப்பு','Apply for LT electricity connection',    13,'utilities',500,200,30,'active','https://tangedco.gov.in','https://tangedco.gov.in'),
  (gen_random_uuid(),'SVC-OLD-RECORD', 'Old Document Retrieval',            'பழைய ஆவண மீட்பு', 'Request copies of old revenue/court records',1,'document',  100,20,15,'active','https://esevai.gov.in','https://esevai.gov.in')
ON CONFLICT DO NOTHING;

-- ── Dataset registry entries ──────────────────────────────────
INSERT INTO system.dataset_registry
  (dataset_id, source_id, dataset_name, description, file_format,
   download_date, record_count, processing_status, validation_status,
   quality_completeness, quality_accuracy, quality_consistency, quality_freshness)
VALUES
  (gen_random_uuid(),
   (SELECT source_id FROM system.source_registry WHERE source_code='TN_GOV_PORTAL' LIMIT 1),
   'Tamil Nadu Administrative Boundaries 2024',
   'District, Taluk, Local Body and Ward level administrative boundaries',
   'GeoJSON', '2024-01-01', 38, 'loaded', 'validated', 1.0, 1.0, 1.0, 0.9),
  (gen_random_uuid(),
   (SELECT source_id FROM system.source_registry WHERE source_code='TN_WELFARE' LIMIT 1),
   'Tamil Nadu Government Schemes 2024',
   'All active state government schemes with eligibility and benefits',
   'JSON', '2024-06-01', 30, 'loaded', 'validated', 0.95, 0.95, 0.95, 0.9),
  (gen_random_uuid(),
   (SELECT source_id FROM system.source_registry WHERE source_code='TN_REVENUE' LIMIT 1),
   'e-Sevai Services Catalogue 2024',
   'Complete list of e-Sevai citizen services with fees and SLAs',
   'JSON', '2024-06-01', 20, 'loaded', 'validated', 0.95, 0.95, 0.95, 0.9)
ON CONFLICT DO NOTHING;
