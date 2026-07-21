<?php

namespace App\Enums;

/** Imaging & media kinds a consultation can reference (object keys in the S3 data lake). */
enum AttachmentKind: string
{
    case Xray = 'xray';
    case Ultrasound = 'ultrasound';       // 2D/3D/4D clips or stills
    case Mri = 'mri';
    case Ecg = 'ecg';
    case LabResult = 'lab_result';
    case ConsultationVideo = 'consultation_video';
    case ConsultationAudio = 'consultation_audio';
    case Other = 'other';
}
