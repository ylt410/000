#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

static const struct {const char *ext;uint32_t legacy,enhanced;} pgResourceVersions[]={{"yft",162,171},{"ydr",165,159},{"ydd",165,159},{"ytd",13,5}};
static bool pg_resource_version_problem(const char *name,uint32_t version,char *why,size_t n){
  const char *dot=strrchr(name,'.');if(!dot)return false;
  for(size_t i=0;i<sizeof pgResourceVersions/sizeof *pgResourceVersions;i++){
    if(strcasecmp(dot+1,pgResourceVersions[i].ext)||version==pgResourceVersions[i].legacy)continue;
    const char *base=strrchr(name,'/');base=base?base+1:name;
    if(version==pgResourceVersions[i].enhanced)snprintf(why,n,"made for GTA V Enhanced (%s is version %u, this game reads %u; install the mod's Legacy (original PC) version)",base,version,pgResourceVersions[i].legacy);
    else snprintf(why,n,"made for another game version (%s is version %u, this game reads %u)",base,version,pgResourceVersions[i].legacy);
    return true;
  }
  return false;
}
static bool pg_rpf_version_problem(FILE *file,uint64_t base,int depth,char *why,size_t n){
  uint32_t header[4];
  if(fseeko(file,(off_t)base,SEEK_SET)||fread(header,4,4,file)!=4||header[0]!=0x52504637)return false;
  if(header[3]&&header[3]!=0x4E45504F)return false;                  // encrypted: can't be read here
  uint32_t count=header[1],namesLength=header[2];
  if(!count||count>500000||namesLength>64u<<20)return false;
  uint64_t *entries=malloc(16ull*count);char *names=malloc(namesLength+1);bool problem=false;
  if(entries&&names&&fread(entries,16,count,file)==count&&fread(names,1,namesLength,file)==namesLength){
    names[namesLength]=0;
    for(uint32_t i=1;i<count&&!problem;i++){
      uint64_t e=entries[2*i];uint32_t offset=(uint32_t)((e>>40)&0x7FFFFF),nameAt=(uint32_t)(e&0xFFFF);
      if(offset==0x7FFFFF||nameAt>=namesLength)continue;
      const char *name=names+nameAt;
      if(e>>63){
        uint32_t system=(uint32_t)entries[2*i+1],graphics=(uint32_t)(entries[2*i+1]>>32);
        problem=pg_resource_version_problem(name,(((system>>28)&0xF)<<4)|((graphics>>28)&0xF),why,n);
      }else if(depth<4){
        size_t length=strlen(name);
        if(length>4&&!strcasecmp(name+length-4,".rpf"))problem=pg_rpf_version_problem(file,base+512ull*offset,depth+1,why,n);
      }
    }
  }
  free(entries);free(names);return problem;
}
bool PGModFileProblem(const char *path,char *why,size_t n){
  FILE *file=fopen(path,"rb");if(!file)return false;
  uint32_t header[4]={0};bool problem=false;
  if(fread(header,4,4,file)==4){
    if(header[0]==0x37435352)problem=pg_resource_version_problem(path,header[1],why,n);
    // An archive saved with no encryption at all (key 0; OpenIV saves OPEN, some RPF tools save none) stops
    // the engine: "Unencrypted archives no longer supported" (log 1121, a PC audio archive).
    else if(header[0]==0x52504637&&header[3]==0){snprintf(why,n,"an archive saved without encryption, which this game can't read (re-save it with OpenIV, or use the original file)");problem=true;}
    else if(header[0]==0x52504637)problem=pg_rpf_version_problem(file,0,0,why,n);
  }
  fclose(file);return problem;
}
