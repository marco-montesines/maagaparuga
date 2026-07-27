<?php

namespace App\Enums;

enum CareContext: string
{
    case Elderly = 'elderly';
    case Sick = 'sick';
    case TerminallyIll = 'terminally_ill';
    case Autistic = 'autistic';
    case General = 'general';
}
