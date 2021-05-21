TYPE_RESIDENTIAL = "Residential"
TYPE_COMMERCIAL = "Commercial"
TYPE_RESIDENTIAL_MULTI = "Multi-Family"

SUBTYPE_CONDO = "Condo"
SUBTYPE_LAND = "Land"
SUBTYPE_HOUSE = "House"
SUBTYPE_HOUSE_MULTIFAMILY = "House-Multi-Family"
SUBTYPE_CONDO_MULTIFAMILY = "Condo-Multi-Family"
SUBTYPE_MULTIFAMILY = "Multi-Family"
SUBTYPE_OTHER = "Other"
SUBTYPE_OFFICE = "Office"
SUBTYPE_INDUSTRIAL = "Industrial"
SUBTYPE_RETAIL = "Retail"

TYPE_SUBTYPE_MAP = {
    TYPE_RESIDENTIAL: [
        SUBTYPE_HOUSE, SUBTYPE_CONDO,
        SUBTYPE_HOUSE_MULTIFAMILY,
        SUBTYPE_CONDO_MULTIFAMILY
    ],
    TYPE_COMMERCIAL: [
        SUBTYPE_MULTIFAMILY, SUBTYPE_OFFICE, SUBTYPE_LAND,
        SUBTYPE_RETAIL, SUBTYPE_INDUSTRIAL, SUBTYPE_OTHER
    ]
}

TYPE_CHOICES = [
    (TYPE_RESIDENTIAL, "Residential"),
    (TYPE_COMMERCIAL, "Commercial")
]

TYPE_PRICES_MAP = {
    TYPE_RESIDENTIAL: 1000, # in cents
    TYPE_COMMERCIAL: 2000, # in cents
    SUBTYPE_HOUSE_MULTIFAMILY: 2000, # in cents
    SUBTYPE_CONDO_MULTIFAMILY: 2000
}

SUBTYPE_CHOICES = [
    (SUBTYPE_CONDO, "Condo"),
    (SUBTYPE_LAND, "Land"),
    (SUBTYPE_HOUSE, "House"),
    (SUBTYPE_MULTIFAMILY, "Multi-Family"),
    (SUBTYPE_OTHER, "Other"),
    (SUBTYPE_OFFICE, "Office"),
    (SUBTYPE_INDUSTRIAL, "Industrial"),
    (SUBTYPE_RETAIL, "Retail"),
    (SUBTYPE_HOUSE_MULTIFAMILY, "House-Multi-Family"),
    (SUBTYPE_CONDO_MULTIFAMILY, "Condo-Multi-Family")
]

STATUS_PENDING = "pending"
STATUS_UPLOADING = "uploading"
STATUS_INACTIVE = "inactive"
STATUS_ACTIVE = "active"
STATUS_SOLD = "sold"
STATUS_DELETED = "deleted"

STATUS_CHOICES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_INACTIVE, "Inactive"),
    (STATUS_ACTIVE, "Active"),
    (STATUS_SOLD, "Sold"),
    (STATUS_DELETED, "Deleted"),
]

TRANSLATION_TRANSLATED = "translated"
TRANSLATION_OUTDATED = "outdated"
TRANSLATION_SCHEDULED = "scheduled"
TRANSLATION_PROCESSING = "processing"
TRANSLATION_CHOICES = (
    (TRANSLATION_TRANSLATED, "Translated"),
    (TRANSLATION_OUTDATED, "Outdated"),
    (TRANSLATION_SCHEDULED, "Scheduled"),
    (TRANSLATION_PROCESSING, "Processing"),
)

# Translations
RENT = 'rent'
TR_FOR_SALE_IN = 'forSaleIn'
TR_FOR_RENT_IN = 'forRentIn'
TR_WITH_DASHES = {
    "multi-family": "multiFamily",
    "condo-multi-family": "condoMultiFamily",
    "house-multi-family": "houseMultiFamily",
}
TR_DEFAULT_DESCRIPTION = 'defaultDescription'

FILE_STATUS_UPLOADED = 'uploaded'
FILE_STATUS_ERROR = 'error'

PROPERTIES_FILE_STATUSES = (
    (STATUS_PENDING, 'pending'),
    (STATUS_UPLOADING, 'uploading'),
    (FILE_STATUS_UPLOADED, 'uploaded'),
    (FILE_STATUS_ERROR, 'error')
)

# Countries lists for advanced search
MULTI_COUNTRY_NAMES = {
    'United States': ['USA', 'United States', 'US', 'America'],
    'Canada': ['Canada'],
    'United Kingdom': [
        'United Kingdom', 'UK', 'England', 'Britain', 'Great Britain'
    ],
    'UAE': ['UAE', 'United Arab Emirates'],
    'Ireland': ['Ireland'],
    'New Zealand': ['New Zealand'],
    'Norway': ['Norwegian', 'Norway'],
    'Philippines': ['Philippines'],
    'Israel': ['Israel', 'State of Israel'],
    'Sweden': ['Sweden'],
    'Switzerland': ['Switzerland'],
    'Germany': ['Germany'],
    'Spain': ['Spain'],
    'Portugal': ['Portugal'],
    'Italy': ['Italy'],
    'Russia': ['Russia'],
    'Greece': ['Greece'],
    'Denmark': ['Denmark'],
    'Finland': ['Finland'],
    'Ukraine': ['Ukraine'],
    'Mexico': ['Mexico'],
    'Saudi Arabia': ['Saudi Arabia'],
    'Netherlands': ['Netherlands'],
    'Luxembourg': ['Luxembourg'],
    'China': ['China'],
    'South Africa': ['South Africa'],
    'Singapore': ['Singapore'],
    'Belgium': ['Belgium'],
    'India': ['India'],
    'Macau': ['Macau', 'Macao'],
    'Qatar': ['Qatar'],
    'Taiwan': ['Taiwan'],
    'Bahrain': ['Bahrain'],
    'Australia': ['Australia'],
    'Fiji': ['Fiji'],
    'France': ['France'],
}
